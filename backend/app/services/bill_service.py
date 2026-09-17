from __future__ import annotations

from calendar import monthrange
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import List, Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.bank_account import BankAccount
from app.models.credit_card_bill import CreditCardBill, CreditCardBillStatus
from app.models.payable import Payable, PayableStatus
from app.services import open_bill_service


def list_bills(
    db: Session, user_id: UUID, month: Optional[int] = None, year: Optional[int] = None
) -> List[CreditCardBill]:
    query = select(CreditCardBill).where(CreditCardBill.user_id == user_id)

    if month is not None and year is not None:
        start_date = date(year, month, 1)
        end_date = date(year, month, monthrange(year, month)[1])
        query = query.where(
            CreditCardBill.due_date >= start_date, CreditCardBill.due_date <= end_date
        )

    result = db.execute(query.order_by(CreditCardBill.due_date.asc()))
    return result.scalars().all()


def _first_day_of_next_month(d: date) -> date:
    if d.month == 12:
        return date(d.year + 1, 1, 1)
    return date(d.year, d.month + 1, 1)


def is_in_payable_window(due_date: date, today: Optional[date] = None) -> bool:
    """A fatura está na janela acionável (mês atual ou o seguinte)?

    A Pluggy devolve o histórico inteiro do cartão e, em alguns bancos, também
    faturas **projetadas** de parcelamento — um cartão do Inter veio com 48
    faturas, a mais distante vencendo quase um ano à frente. Gerar `Payable`
    para todas polui a lista de contas a pagar em duas pontas: faturas antigas
    que a conciliação não casou viram "vencida" fantasma, e as projeções futuras
    mostram valores que ainda vão mudar.

    Fora da janela a fatura continua salva como `CreditCardBill` — o histórico
    segue disponível para análise, só não vira obrigação a pagar.
    """
    today = today or date.today()
    start = date(today.year, today.month, 1)
    next_month = _first_day_of_next_month(start)
    end = date(next_month.year, next_month.month, monthrange(next_month.year, next_month.month)[1])
    return start <= due_date <= end


def _bill_is_really_closed(bill_data: dict, due_date: date, today: date) -> bool:
    """A Bills API pode devolver fatura que ainda não fechou de verdade.

    O Inter projeta com meses de antecedência e **nunca** preenche
    `billClosingDate` (confirmado direto na API, inclusive em faturas já
    vencidas) — tratar qualquer entrada da Bills API como definitiva
    gravava fatura futura como `CLOSED` (a UI mostra "Fechada") com um
    valor que ainda pode mudar até o ciclo realmente fechar.

    `billClosingDate` presente é o sinal direto de fechamento real (Itaú
    preenche a partir de ~7 dias antes do vencimento). Ausente — caso do
    Inter — cai no fallback: só confia que fechou se o vencimento já
    passou.
    """
    if bill_data.get("billClosingDate"):
        return True
    return due_date <= today


def upsert_bill(
    db: Session,
    user_id: UUID,
    account: BankAccount,
    pluggy_account_id: str,
    bill_data: dict,
    card_name: Optional[str] = None,
    today: Optional[date] = None,
) -> CreditCardBill:
    today = today or date.today()
    external_id = str(bill_data["id"])
    due_date = datetime.fromisoformat(bill_data["dueDate"].replace("Z", "+00:00")).date()
    total_amount = Decimal(str(bill_data.get("totalAmount") or 0))
    minimum_payment = bill_data.get("minimumPaymentAmount")
    allows_installments = bill_data.get("allowsInstallments")
    status = (
        CreditCardBillStatus.CLOSED
        if _bill_is_really_closed(bill_data, due_date, today)
        else CreditCardBillStatus.OPEN
    )

    bill = db.execute(
        select(CreditCardBill).where(
            CreditCardBill.user_id == user_id,
            CreditCardBill.external_id == external_id,
        )
    ).scalar_one_or_none()

    if bill is None:
        # A Pluggy pode reemitir um novo external_id para a mesma fatura entre
        # syncs (observado em sandbox). Como um cartão só tem uma fatura por
        # mês, tratamos uma fatura já existente do mesmo cartão no mesmo
        # mês/ano como a mesma fatura em vez de duplicar.
        bill = db.execute(
            select(CreditCardBill).where(
                CreditCardBill.user_id == user_id,
                CreditCardBill.pluggy_account_id == pluggy_account_id,
                CreditCardBill.due_date >= due_date.replace(day=1),
                CreditCardBill.due_date < _first_day_of_next_month(due_date),
            )
        ).scalar_one_or_none()
        if bill is not None:
            bill.external_id = external_id

    # Herda as personalizações do cartão (apelido e cor) se já existirem para
    # este pluggy_account_id — são do cartão, não da fatura individual.
    existing_custom = (
        db.execute(
            select(CreditCardBill.custom_card_name).where(
                CreditCardBill.user_id == user_id,
                CreditCardBill.pluggy_account_id == pluggy_account_id,
                CreditCardBill.custom_card_name.isnot(None),
            )
        )
        .scalars()
        .first()
    )
    existing_color = (
        db.execute(
            select(CreditCardBill.custom_color_hex).where(
                CreditCardBill.user_id == user_id,
                CreditCardBill.pluggy_account_id == pluggy_account_id,
                CreditCardBill.custom_color_hex.isnot(None),
            )
        )
        .scalars()
        .first()
    )

    if bill is None:
        bill = CreditCardBill(
            user_id=user_id,
            bank_account_id=account.id,
            pluggy_account_id=pluggy_account_id,
            external_id=external_id,
            card_name=card_name,
            custom_card_name=existing_custom,
            custom_color_hex=existing_color,
            due_date=due_date,
            total_amount=total_amount,
            status=status,
            minimum_payment_amount=(
                Decimal(str(minimum_payment)) if minimum_payment is not None else None
            ),
            allows_installments=allows_installments,
        )
        db.add(bill)
        db.flush()
    else:
        # Vindo da Bills API, o valor é o mais oficial disponível — mas só é
        # realmente definitivo (`CLOSED`) quando _bill_is_really_closed diz
        # que sim; senão é uma projeção do banco (ex: Inter), tratada como
        # `OPEN` igual a uma reconstrução nossa (mesmo aviso de estimativa
        # na UI), só que com o valor vindo direto do banco em vez de somado
        # por nós.
        bill.status = status
        bill.due_date = due_date
        bill.total_amount = total_amount
        bill.minimum_payment_amount = (
            Decimal(str(minimum_payment)) if minimum_payment is not None else None
        )
        bill.allows_installments = allows_installments
        if card_name:
            bill.card_name = card_name
        if existing_custom:
            bill.custom_card_name = existing_custom
        if existing_color:
            bill.custom_color_hex = existing_color

    bill.synced_at = datetime.now(timezone.utc)

    _sync_payable(db, bill, account, today=today)

    db.commit()
    db.refresh(bill)
    return bill


def upsert_open_bill(
    db: Session,
    user_id: UUID,
    account: BankAccount,
    pluggy_account_id: str,
    transactions: List[dict],
    card_name: Optional[str] = None,
    today: Optional[date] = None,
) -> Optional[CreditCardBill]:
    """Reconstrói e salva a fatura do ciclo em aberto deste cartão.

    Só faz sentido quando existe uma fatura fechada anterior: é dela que saem o
    dia de vencimento do cartão e o corte que separa o ciclo novo do anterior.
    Se o banco já publicou a fatura do próximo vencimento (caso do Inter, que
    projeta com meses de antecedência), não há ciclo em aberto a estimar.
    """
    today = today or date.today()

    # A última FECHADA de verdade é a última já VENCIDA, não a de vencimento
    # mais distante: o Inter publica faturas projetadas com quase um ano de
    # antecedência (todas CLOSED, porque a Bills API já as conhece), e pegar
    # a mais distante fazia o ciclo-alvo cair anos à frente — sem nenhuma
    # transação que caísse nele, reconstruindo a fatura aberta como R$ 0,00
    # (issue #84).
    closed = (
        db.execute(
            select(CreditCardBill)
            .where(
                CreditCardBill.user_id == user_id,
                CreditCardBill.pluggy_account_id == pluggy_account_id,
                CreditCardBill.status == CreditCardBillStatus.CLOSED,
                CreditCardBill.due_date <= today,
            )
            .order_by(CreditCardBill.due_date.desc())
        )
        .scalars()
        .first()
    )

    if closed is None:
        return None

    target_due = open_bill_service.next_due_date(closed.due_date, today)
    if target_due <= closed.due_date:
        return None

    # O Inter publica faturas projetadas com quase um ano de antecedência, então
    # "o mês seguinte à última fechada" cai em 2027 — não existe ciclo aberto a
    # estimar ali. A mesma janela que decide se uma fatura vira Payable serve
    # aqui: fora dela não é o ciclo corrente.
    if not is_in_payable_window(target_due, today):
        return None

    amount = open_bill_service.compute_open_bill_amount(transactions, target_due, closed.due_date)

    bill = db.execute(
        select(CreditCardBill).where(
            CreditCardBill.user_id == user_id,
            CreditCardBill.pluggy_account_id == pluggy_account_id,
            CreditCardBill.due_date >= target_due.replace(day=1),
            CreditCardBill.due_date < _first_day_of_next_month(target_due),
        )
    ).scalar_one_or_none()

    if bill is not None and (
        bill.status == CreditCardBillStatus.CLOSED or not bill.external_id.startswith("open:")
    ):
        # `status == CLOSED`: o banco fechou a fatura desse vencimento entre
        # um sync e outro — o valor oficial manda, nada a estimar.
        # `external_id` "real" (não é o synthetic "open:..." que só esta
        # função gera): a Bills API já deu um valor pra este ciclo mesmo sem
        # fechar de verdade (projeção do Inter, ver _bill_is_really_closed)
        # — o valor do banco, mesmo cedo, é melhor que nossa soma de
        # transações, que sofre do mesmo gap de rolagem de competência
        # (issue #85).
        return bill

    if bill is None:
        bill = CreditCardBill(
            user_id=user_id,
            bank_account_id=account.id,
            pluggy_account_id=pluggy_account_id,
            external_id=f"open:{pluggy_account_id}:{target_due:%Y-%m}",
            card_name=card_name,
            custom_card_name=closed.custom_card_name,
            custom_color_hex=closed.custom_color_hex,
            due_date=target_due,
            total_amount=amount,
            status=CreditCardBillStatus.OPEN,
        )
        db.add(bill)
    else:
        bill.due_date = target_due
        bill.total_amount = amount
        if card_name:
            bill.card_name = card_name
        bill.custom_card_name = closed.custom_card_name
        bill.custom_color_hex = closed.custom_color_hex

    bill.synced_at = datetime.now(timezone.utc)
    # A obrigação existe desde que o ciclo abre; o valor é atualizado a cada
    # sync enquanto o payable estiver PENDING, e congela quando a fatura fecha.
    # `today` precisa descer até aqui: a janela acionável é a mesma que decidiu
    # reconstruir o ciclo, e sem isso um teste que injeta uma data fixa via
    # `today=` deixa de gerar o payable quando a data real do sistema passa.
    _sync_payable(db, bill, account, today=today)
    db.commit()
    db.refresh(bill)
    return bill


# Achado na revisão do PR da issue #25: `accounts_list` pode devolver uma
# resposta parcial (não vazia, só incompleta — glitch transitório da Pluggy)
# omitindo um cartão que continua ativo. Retirar na primeira passada em que
# ele não aparece apagaria fatura/payable reais por causa de uma falha de
# rede, não de um cancelamento de verdade. `synced_at` (grava a cada sync
# bem-sucedido) já existe no modelo — usado como carência: só retira quem
# ficou "sumido" por mais de um ciclo inteiro de sync (o cron diário roda
# uma vez por dia; webhooks disparam mais frequente ainda).
_RETIRE_GRACE_PERIOD = timedelta(days=2)


def retire_vanished_open_bills(
    db: Session,
    user_id: UUID,
    account: BankAccount,
    seen_pluggy_account_ids: set[str],
    *,
    now: Optional[datetime] = None,
) -> int:
    """Cartão cancelado/desativado some da resposta da Pluggy pro item, mas
    nada parava de gerar conta a pagar pra ele (issue #25) — a fatura em
    aberto (reconstruída de transações) continuava lá, PENDING pra sempre.

    Só mexe em `CreditCardBill` **OPEN**: `CLOSED` é o valor oficial que o
    banco já fechou, histórico válido mesmo se o cartão for cancelado depois
    — nunca é retirado. O `Payable` ligado só é removido se ainda `PENDING`;
    um já `PAID` nunca é tocado (é obrigação que já foi honrada).

    `seen_pluggy_account_ids` vazio (a Pluggy não devolveu nenhuma conta pro
    item nesta passada) é tratado como sinal ambíguo, não "tudo sumiu" — um
    glitch transitório não pode apagar fatura/payable de todo mundo; quem
    chama já pula esta função nesse caso.
    """
    now = now or datetime.now(timezone.utc)
    ghost_bills = (
        db.execute(
            select(CreditCardBill).where(
                CreditCardBill.user_id == user_id,
                CreditCardBill.bank_account_id == account.id,
                CreditCardBill.status == CreditCardBillStatus.OPEN,
                CreditCardBill.pluggy_account_id.not_in(seen_pluggy_account_ids),
            )
        )
        .scalars()
        .all()
    )

    retired = 0
    for bill in ghost_bills:
        synced_at = bill.synced_at
        if synced_at.tzinfo is None:
            synced_at = synced_at.replace(tzinfo=timezone.utc)
        if now - synced_at < _RETIRE_GRACE_PERIOD:
            # sumiu só nesta passada — pode ser um glitch, dá mais uma chance
            continue

        if bill.payable_id is not None:
            payable = db.get(Payable, bill.payable_id)
            if payable is not None and payable.status == PayableStatus.PENDING:
                db.delete(payable)
        db.delete(bill)
        retired += 1

    if retired:
        db.commit()

    return retired


def update_bill_customization(
    db: Session, user_id: UUID, bill_id: UUID, changes: dict
) -> Optional[CreditCardBill]:
    """Aplica apelido e/ou cor a **todas** as faturas do mesmo cartão.

    `changes` traz só os campos que o cliente mandou (`exclude_unset`): editar a
    cor não pode apagar o apelido, e vice-versa. Um campo presente com `None`
    é uma limpeza explícita.
    """
    bill = db.execute(
        select(CreditCardBill).where(
            CreditCardBill.id == bill_id, CreditCardBill.user_id == user_id
        )
    ).scalar_one_or_none()

    if bill is None:
        return None

    if "custom_card_name" in changes:
        raw = changes["custom_card_name"]
        changes["custom_card_name"] = raw.strip() if raw and raw.strip() else None

    all_bills = (
        db.execute(
            select(CreditCardBill).where(
                CreditCardBill.user_id == user_id,
                CreditCardBill.pluggy_account_id == bill.pluggy_account_id,
            )
        )
        .scalars()
        .all()
    )

    for b in all_bills:
        for field, value in changes.items():
            setattr(b, field, value)
        db.add(b)
        _sync_payable(db, b, b.bank_account)

    db.commit()
    db.refresh(bill)
    return bill


def _sync_payable(
    db: Session,
    bill: CreditCardBill,
    account: BankAccount,
    today: Optional[date] = None,
) -> None:
    label = bill.custom_card_name or bill.card_name or account.name
    title = f"Fatura {label} — {bill.due_date.strftime('%m/%Y')}"

    if bill.payable_id is None:
        # Só a criação é filtrada: um payable que já existe continua sendo
        # mantido em sincronia mesmo que a fatura tenha saído da janela.
        if not is_in_payable_window(bill.due_date, today):
            return

        payable = Payable(
            user_id=bill.user_id,
            title=title,
            amount=bill.total_amount,
            due_date=bill.due_date,
            status=PayableStatus.PENDING,
        )
        db.add(payable)
        db.flush()
        bill.payable_id = payable.id
        db.add(bill)
        return

    payable = db.get(Payable, bill.payable_id)
    if payable is None:
        return

    # O título é só rótulo, então é corrigido mesmo em fatura já paga: payables
    # criados antes de `card_name` existir ficaram todos como "Fatura {nome da
    # conexão}", e com o conector MeuPluggy isso deixa dois cartões do mesmo mês
    # com título idêntico e indistinguível. Valor e vencimento, não — são fatos
    # de uma fatura já liquidada e não devem ser reescritos.
    payable.title = title
    if payable.status == PayableStatus.PENDING:
        payable.amount = bill.total_amount
        payable.due_date = bill.due_date
    db.add(payable)
