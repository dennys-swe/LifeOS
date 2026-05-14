from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from decimal import Decimal
from typing import List
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.payable import Payable, PayableStatus
from app.models.transaction import Transaction, TransactionType
from app.schemas.reconciliation import ReconciliationSuggestionResponse

AMOUNT_TOLERANCE = Decimal("0.05")
DATE_TOLERANCE_DAYS = 7


def _amount_in_range(payable_amount: Decimal, tx_amount: Decimal) -> bool:
    lower = payable_amount * (1 - AMOUNT_TOLERANCE)
    upper = payable_amount * (1 + AMOUNT_TOLERANCE)
    return lower <= tx_amount <= upper


def _compute_score(exact_amount: bool, exact_date: bool) -> float:
    if exact_amount and exact_date:
        return 1.0
    if exact_amount and not exact_date:
        return 0.8
    if not exact_amount and exact_date:
        return 0.6
    return 0.5


def suggest_reconciliation(
    db: Session,
    transactions: List[Transaction],
) -> List[ReconciliationSuggestionResponse]:
    pending_payables = db.execute(
        select(Payable).where(Payable.status == PayableStatus.PENDING)
    ).scalars().all()

    suggestions: List[ReconciliationSuggestionResponse] = []

    for tx in transactions:
        if tx.type != TransactionType.EXPENSE:
            continue

        tx_amount = Decimal(str(tx.amount))

        for payable in pending_payables:
            p_amount = Decimal(str(payable.amount))
            exact_amount = tx_amount == p_amount
            approx_amount = _amount_in_range(p_amount, tx_amount)

            if not exact_amount and not approx_amount:
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

    suggestions.sort(key=lambda s: s.confidence_score, reverse=True)
    return suggestions


def confirm_reconciliation(
    db: Session,
    transaction_id: UUID,
    payable_id: UUID,
) -> Payable:
    payable = db.get(Payable, payable_id)
    if payable is None:
        raise ValueError(f"Payable {payable_id} not found")

    transaction = db.get(Transaction, transaction_id)
    if transaction is None:
        raise ValueError(f"Transaction {transaction_id} not found")

    payable.status = PayableStatus.PAID
    payable.payment_date = transaction.date
    payable.transaction_id = transaction_id

    db.add(payable)
    db.commit()
    db.refresh(payable)
    return payable
