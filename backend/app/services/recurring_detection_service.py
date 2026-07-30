from __future__ import annotations

import re
import statistics
from collections import Counter, defaultdict
from decimal import Decimal
from typing import List
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.recurring_payable import RecurringPayable
from app.models.transaction import Transaction, TransactionType
from app.schemas.recurring_detection import RecurringSuggestion

MIN_DISTINCT_MONTHS = 3
AMOUNT_TOLERANCE = 0.10
MAX_DAY_DEVIATION = 3

_NORMALIZE_RE = re.compile(r"[0-9]+|\s+")


def _normalize_description(description: str) -> str:
    collapsed = _NORMALIZE_RE.sub(" ", description.upper())
    return collapsed.strip()


def detect_recurring_candidates(db: Session, user_id: UUID) -> List[RecurringSuggestion]:
    transactions = db.execute(
        select(Transaction).where(
            Transaction.user_id == user_id,
            Transaction.type == TransactionType.EXPENSE,
            # Transferência recorrente entre as próprias contas não é conta a
            # pagar — e é volumosa (219 "Same person transfer" no extrato real
            # do dono), então dominava as sugestões.
            Transaction.is_transfer.is_(False),
        )
    ).scalars().all()

    existing_titles = {
        rec.title.strip().upper()
        for rec in db.execute(
            select(RecurringPayable).where(RecurringPayable.user_id == user_id)
        ).scalars().all()
    }

    groups: dict[str, list[Transaction]] = defaultdict(list)
    for tx in transactions:
        key = _normalize_description(tx.description)
        if not key:
            continue
        groups[key].append(tx)

    suggestions: List[RecurringSuggestion] = []

    for key, txs in groups.items():
        distinct_months = {(tx.date.year, tx.date.month) for tx in txs}
        if len(distinct_months) < MIN_DISTINCT_MONTHS:
            continue

        amounts = [Decimal(str(tx.amount)) for tx in txs]
        median_amount = Decimal(str(statistics.median(amounts)))
        if median_amount <= 0:
            continue
        lower = median_amount * Decimal(str(1 - AMOUNT_TOLERANCE))
        upper = median_amount * Decimal(str(1 + AMOUNT_TOLERANCE))
        if any(a < lower or a > upper for a in amounts):
            continue

        days = [tx.date.day for tx in txs]
        day_mode = Counter(days).most_common(1)[0][0]
        if any(abs(day - day_mode) > MAX_DAY_DEVIATION for day in days):
            continue

        title = Counter(tx.description.strip() for tx in txs).most_common(1)[0][0]
        if title.strip().upper() in existing_titles:
            continue

        suggestions.append(
            RecurringSuggestion(
                title=title,
                amount=median_amount,
                day_of_month=day_mode,
                occurrences=len(txs),
                distinct_months=len(distinct_months),
            )
        )

    suggestions.sort(key=lambda s: s.occurrences, reverse=True)
    return suggestions
