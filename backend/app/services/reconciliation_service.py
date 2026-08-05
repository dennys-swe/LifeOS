from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from decimal import Decimal
from typing import List
from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models.credit_card_bill import CreditCardBill
from app.models.payable import Payable, PayableStatus
from app.models.transaction import Transaction, TransactionType
from app.schemas.reconciliation import ReconciliationSuggestionResponse
from app.services.pluggy_category_map import CREDIT_CARD_PAYMENT

DATE_TOLERANCE_DAYS = 7

# Descrições "eco" que o banco/Pluggy lança de forma genérica sempre que uma
# fatura de cartão é paga — além do débito real (ex: "FATURA PAGA ITAU
# MULTIPL", "Pagamento de boleto INT LUIZA MC"), aparece uma segunda transação
# com um desses textos fixos, no mesmo valor. Não é ambiguidade real: é o
# mesmo evento contado duas vezes.
GENERIC_BILL_PAYMENT_ECHOES = {"PAGAMENTO RECEBIDO", "PAGAMENTO COM SALDO"}


def _reconcilable(tx: Transaction) -> bool:
    """Uma transação pode quitar um payable?

    Além das despesas, inclui a quitação de fatura: do lado do **cartão** ela
    vem como `type=CREDIT` da Pluggy (o pagamento entra no cartão), então viraria
    INCOME e sairia da conciliação — mas é exatamente ela que casa com o payable
    da fatura quando a conta de onde saiu o dinheiro não está conectada.
    `_confirm_bill_payment_echoes` já sabe preferir o débito real quando as duas
    pontas aparecem.
    """
    return (
        tx.type == TransactionType.EXPENSE
        or tx.external_category == CREDIT_CARD_PAYMENT
    )


def _is_reconcilable():
    """Versão SQL de `_reconcilable`, para filtrar na query."""
    return or_(
        Transaction.type == TransactionType.EXPENSE,
        Transaction.external_category == CREDIT_CARD_PAYMENT,
    )


def _compute_score(exact_amount: bool, exact_date: bool) -> float:
    """Só existem dois níveis: o valor sempre bate exato (ver `suggest_reconciliation`),
    então o que separa 1.0 de 0.8 é a data cair no vencimento ou dentro da janela.
    Os níveis 0.6/0.5, de valor aproximado, foram removidos por gerarem falso
    positivo em quase toda sugestão."""
    return 1.0 if exact_amount and exact_date else 0.8


def suggest_pending(db: Session, user_id: UUID) -> List[ReconciliationSuggestionResponse]:
    """Sugestões de conciliação sobre todo o histórico não conciliado do usuário —
    usado pela tela de Bancos & Faturas para mostrar confirmações pendentes mesmo
    fora do fluxo de um sync específico (ex: sync rodado em background).

    Também roda a auto-reconciliação sobre esse histórico completo antes de
    devolver a lista — o auto-reconcile do sync só enxerga as transações
    recém-importadas daquele request, então casos óbvios (ex: eco de
    pagamento de fatura) de transações mais antigas só se resolvem aqui."""
    unreconciled = db.execute(
        select(Transaction).where(
            Transaction.user_id == user_id,
            _is_reconcilable(),
            ~Transaction.id.in_(
                select(Payable.transaction_id).where(
                    Payable.user_id == user_id, Payable.transaction_id.is_not(None)
                )
            ),
        )
    ).scalars().all()
    suggestions = suggest_reconciliation(db, user_id, unreconciled)
    auto_confirmed = auto_reconcile_confident_matches(db, user_id, suggestions)
    return drop_resolved_payables(suggestions, auto_confirmed)


def drop_resolved_payables(
    suggestions: List[ReconciliationSuggestionResponse], confirmed_transaction_ids: List[UUID]
) -> List[ReconciliationSuggestionResponse]:
    """Uma vez que um payable foi resolvido pelo auto-reconcile, qualquer outro
    candidato pendente pra ele (ex: o eco genérico que não foi o escolhido)
    também deixa de fazer sentido — não só a sugestão que efetivamente confirmou."""
    confirmed_ids = set(confirmed_transaction_ids)
    resolved_payable_ids = {s.payable_id for s in suggestions if s.transaction_id in confirmed_ids}
    return [s for s in suggestions if s.payable_id not in resolved_payable_ids]


def suggest_reconciliation(
    db: Session,
    user_id: UUID,
    transactions: List[Transaction],
) -> List[ReconciliationSuggestionResponse]:
    pending_payables = db.execute(
        select(Payable).where(
            Payable.user_id == user_id, Payable.status == PayableStatus.PENDING
        )
    ).scalars().all()

    suggestions: List[ReconciliationSuggestionResponse] = []

    for tx in transactions:
        if not _reconcilable(tx):
            continue

        tx_amount = Decimal(str(tx.amount))

        for payable in pending_payables:
            p_amount = Decimal(str(payable.amount))
            exact_amount = tx_amount == p_amount

            # Valor aproximado foi abandonado: medido contra os 91 payables já
            # pagos do dono, a tolerância de ±5% achava 55 (60%) contra 51 (56%)
            # do valor exato — 4 acertos a mais. Em troca, casava qualquer
            # compra de valor parecido na janela de datas: a conta de água de
            # R$ 14 batia com farmácia, encargo e posto, e as 5 sugestões
            # pendentes eram todas falsas. Precisão vale mais que 4% de recall
            # numa tela que pede confirmação manual.
            if not exact_amount:
                continue

            date_diff = abs((payable.due_date - tx.date).days)
            exact_date = date_diff == 0
            within_range = date_diff <= DATE_TOLERANCE_DAYS

            if not exact_date and not within_range:
                continue

            score = _compute_score(exact_amount, exact_date)
            suggestions.append(
                ReconciliationSuggestionResponse(
                    transaction_id=tx.id,
                    payable_id=payable.id,
                    confidence_score=score,
                    payable_title=payable.title,
                    payable_amount=p_amount,
                    transaction_description=tx.description,
                    transaction_amount=tx_amount,
                )
            )

    suggestions = _suppress_weaker_amount_matches(suggestions)
    suggestions.sort(key=lambda s: s.confidence_score, reverse=True)
    return suggestions


def _suppress_weaker_amount_matches(
    suggestions: List[ReconciliationSuggestionResponse],
) -> List[ReconciliationSuggestionResponse]:
    """Um match de valor aproximado (0.5/0.6) nunca é melhor palpite que um
    match de valor exato (0.8/1.0) para a mesma fatura — quando os dois
    aparecem juntos, o aproximado é só ruído (ex: um Pix pra outra pessoa que
    coincidiu de valor). Remove os aproximados nesse caso."""
    exact_payables = {s.payable_id for s in suggestions if s.confidence_score >= 0.8}
    return [
        s for s in suggestions
        if s.confidence_score >= 0.8 or s.payable_id not in exact_payables
    ]


def _bill_payable_ids(db: Session, user_id: UUID) -> set[UUID]:
    return set(
        db.execute(
            select(CreditCardBill.payable_id).where(
                CreditCardBill.user_id == user_id, CreditCardBill.payable_id.is_not(None)
            )
        ).scalars().all()
    )


def auto_reconcile_confident_matches(
    db: Session,
    user_id: UUID,
    suggestions: List[ReconciliationSuggestionResponse],
) -> List[UUID]:
    """Confirma automaticamente sugestões com confidence 1.0 quando o match é
    único (nem o payable nem a transação aparecem em mais de uma sugestão
    exata). Retorna os transaction_ids confirmados."""
    exact = [s for s in suggestions if s.confidence_score == 1.0]

    payable_counts: dict[UUID, int] = {}
    transaction_counts: dict[UUID, int] = {}
    for s in exact:
        payable_counts[s.payable_id] = payable_counts.get(s.payable_id, 0) + 1
        transaction_counts[s.transaction_id] = transaction_counts.get(s.transaction_id, 0) + 1

    confirmed: List[UUID] = []
    confirmed_payable_ids: set[UUID] = set()
    for s in exact:
        if payable_counts[s.payable_id] != 1 or transaction_counts[s.transaction_id] != 1:
            continue
        try:
            confirm_reconciliation(
                db, user_id, transaction_id=s.transaction_id, payable_id=s.payable_id
            )
            confirmed.append(s.transaction_id)
            confirmed_payable_ids.add(s.payable_id)
        except ValueError:
            continue

    confirmed += _auto_resolve_bill_payment_echoes(
        db, user_id, suggestions, already_confirmed=confirmed_payable_ids
    )
    return confirmed


def _auto_resolve_bill_payment_echoes(
    db: Session,
    user_id: UUID,
    suggestions: List[ReconciliationSuggestionResponse],
    already_confirmed: set[UUID],
) -> List[UUID]:
    """Para faturas de cartão, quando há mais de um candidato de valor exato
    (confidence >= 0.8) e só um deles NÃO é uma descrição-eco genérica
    (GENERIC_BILL_PAYMENT_ECHOES), confirma esse — ele é o débito real, o
    outro é só o registro informativo do banco pro mesmo pagamento."""
    by_payable: dict[UUID, list[ReconciliationSuggestionResponse]] = {}
    for s in suggestions:
        if s.confidence_score >= 0.8 and s.payable_id not in already_confirmed:
            by_payable.setdefault(s.payable_id, []).append(s)

    candidates = {pid: group for pid, group in by_payable.items() if len(group) > 1}
    if not candidates:
        return []

    bill_payable_ids = _bill_payable_ids(db, user_id)

    confirmed: List[UUID] = []
    for payable_id, group in candidates.items():
        if payable_id not in bill_payable_ids:
            continue
        specific = [s for s in group if s.transaction_description.strip().upper() not in GENERIC_BILL_PAYMENT_ECHOES]
        if len(specific) != 1:
            continue
        try:
            confirm_reconciliation(
                db, user_id, transaction_id=specific[0].transaction_id, payable_id=payable_id
            )
            confirmed.append(specific[0].transaction_id)
        except ValueError:
            continue

    return confirmed


def confirm_reconciliation(
    db: Session,
    user_id: UUID,
    transaction_id: UUID,
    payable_id: UUID,
) -> Payable:
    payable = db.execute(
        select(Payable).where(Payable.id == payable_id, Payable.user_id == user_id)
    ).scalar_one_or_none()
    if payable is None:
        raise ValueError(f"Payable {payable_id} not found")

    transaction = db.execute(
        select(Transaction).where(
            Transaction.id == transaction_id, Transaction.user_id == user_id
        )
    ).scalar_one_or_none()
    if transaction is None:
        raise ValueError(f"Transaction {transaction_id} not found")

    payable.status = PayableStatus.PAID
    payable.payment_date = transaction.date
    payable.transaction_id = transaction_id

    db.add(payable)
    db.commit()
    db.refresh(payable)
    return payable
