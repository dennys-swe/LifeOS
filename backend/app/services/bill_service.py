from __future__ import annotations

from calendar import monthrange
from datetime import date, datetime, timezone
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


def upsert_bill(
    db: Session,
    user_id: UUID,
    account: BankAccount,
    pluggy_account_id: str,
    bill_data: dict,
    card_name: Optional[str] = None,
) -> CreditCardBill:
    external_id = str(bill_data["id"])
    due_date = datetime.fromisoformat(bill_data["dueDate"].replace("Z", "+00:00")).date()
    total_amount = Decimal(str(bill_data.get("totalAmount") or 0))
    minimum_payment = bill_data.get("minimumPaymentAmount")
    allows_installments = bill_data.get("allowsInstallments")

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
    existing_custom = db.execute(
        select(CreditCardBill.custom_card_name).where(
            CreditCardBill.user_id == user_id,
            CreditCardBill.pluggy_account_id == pluggy_account_id,
            CreditCardBill.custom_card_name.isnot(None),
        )
    ).scalars().first()
    existing_color = db.execute(
        select(CreditCardBill.custom_color_hex).where(
            CreditCardBill.user_id == user_id,
            CreditCardBill.pluggy_account_id == pluggy_account_id,
            CreditCardBill.custom_color_hex.isnot(None),
        )
    ).scalars().first()

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
            status=CreditCardBillStatus.CLOSED,
            minimum_payment_amount=(
                Decimal(str(minimum_payment)) if minimum_payment is not None else None
            ),
            allows_installments=allows_installments,
        )
        db.add(bill)
        db.flush()
    else:
        # Vindo da Bills API, o valor é oficial: se este registro era a
        # reconstrução do ciclo em aberto, ele agora vira a fatura fechada.
        bill.status = CreditCardBillStatus.CLOSED
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

    _sync_payable(db, bill, account)

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

    closed = db.execute(
        select(CreditCardBill)
        .where(
            CreditCardBill.user_id == user_id,
            CreditCardBill.pluggy_account_id == pluggy_account_id,
            CreditCardBill.status == CreditCardBillStatus.CLOSED,
        )
        .order_by(CreditCardBill.due_date.desc())
    ).scalars().first()

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

    amount = open_bill_service.compute_open_bill_amount(
        transactions, target_due, closed.due_date
    )

    bill = db.execute(
        select(CreditCardBill).where(
            CreditCardBill.user_id == user_id,
            CreditCardBill.pluggy_account_id == pluggy_account_id,
            CreditCardBill.due_date >= target_due.replace(day=1),
            CreditCardBill.due_date < _first_day_of_next_month(target_due),
        )
    ).scalar_one_or_none()

    if bill is not None and bill.status == CreditCardBillStatus.CLOSED:
        # O banco fechou a fatura desse vencimento entre um sync e outro — o
        # valor oficial manda, nada a estimar.
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
    db.commit()
    db.refresh(bill)
    return bill


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

    all_bills = db.execute(
        select(CreditCardBill).where(
            CreditCardBill.user_id == user_id,
            CreditCardBill.pluggy_account_id == bill.pluggy_account_id,
        )
    ).scalars().all()

    for b in all_bills:
        for field, value in changes.items():
            setattr(b, field, value)
        db.add(b)
        _sync_payable(db, b, b.bank_account)

    db.commit()
    db.refresh(bill)
    return bill


def _sync_payable(db: Session, bill: CreditCardBill, account: BankAccount) -> None:
    label = bill.custom_card_name or bill.card_name or account.name
    title = f"Fatura {label} — {bill.due_date.strftime('%m/%Y')}"

    # Fatura em aberto muda de valor a cada compra do ciclo — vira obrigação a
    # pagar só quando o banco fecha. Quando isso acontece o mesmo registro passa
    # a CLOSED e cai no fluxo normal abaixo.
    if bill.status == CreditCardBillStatus.OPEN:
        return

    if bill.payable_id is None:
        # Só a criação é filtrada: um payable que já existe continua sendo
        # mantido em sincronia mesmo que a fatura tenha saído da janela.
        if not is_in_payable_window(bill.due_date):
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

