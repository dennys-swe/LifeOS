from __future__ import annotations

from calendar import monthrange
from datetime import date
from decimal import Decimal
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.category import Category
from app.models.payable import Payable, PayableStatus
from app.models.transaction import Transaction, TransactionType
from app.schemas.summary import CategorySummary, SummaryResponse
from app.services.budget_service import build_budget_map


_UNCATEGORIZED_NAME = "Sem categoria"
_UNCATEGORIZED_COLOR = "#64748B"


def get_summary(db: Session, month: int, year: int) -> SummaryResponse:
    start_date = date(year, month, 1)
    end_date = date(year, month, monthrange(year, month)[1])

    payables = db.execute(
        select(Payable).where(
            Payable.due_date >= start_date,
            Payable.due_date <= end_date,
        )
    ).scalars().all()

    transactions = db.execute(
        select(Transaction).where(
            Transaction.date >= start_date,
            Transaction.date <= end_date,
        )
    ).scalars().all()

    categories = {cat.id: cat for cat in db.execute(select(Category)).scalars().all()}

    total_income = Decimal("0")
    total_expenses = Decimal("0")
    total_pending = Decimal("0")
    total_paid = Decimal("0")

    payables_by_category: dict = {}
    for p in payables:
        key = p.category_id
        payables_by_category[key] = payables_by_category.get(key, Decimal("0")) + Decimal(str(p.amount))
        if p.status == PayableStatus.PENDING:
            total_pending += Decimal(str(p.amount))
        elif p.status == PayableStatus.PAID:
            total_paid += Decimal(str(p.amount))

    transactions_by_category: dict = {}
    for t in transactions:
        key = t.category_id
        transactions_by_category[key] = transactions_by_category.get(key, Decimal("0")) + Decimal(str(t.amount))
        if t.type == TransactionType.INCOME:
            total_income += Decimal(str(t.amount))
        else:
            total_expenses += Decimal(str(t.amount))

    all_keys = set(payables_by_category.keys()) | set(transactions_by_category.keys())
    budget_map = build_budget_map(db, month=month, year=year)

    by_category = []
    for key in all_keys:
        if key and key in categories:
            cat = categories[key]
            name = cat.name
            color = cat.color_hex
        else:
            name = _UNCATEGORIZED_NAME
            color = _UNCATEGORIZED_COLOR

        total_p = payables_by_category.get(key, Decimal("0"))
        budget_limit = budget_map.get(key) if key else None
        budget_used_pct = None
        if budget_limit and budget_limit > 0:
            budget_used_pct = round(float(total_p / budget_limit * 100), 1)

        by_category.append(CategorySummary(
            category_id=key,
            category_name=name,
            color_hex=color,
            total_payables=total_p,
            total_transactions=transactions_by_category.get(key, Decimal("0")),
            budget_limit=budget_limit,
            budget_used_pct=budget_used_pct,
        ))

    by_category.sort(key=lambda c: c.total_payables, reverse=True)

    return SummaryResponse(
        total_income=total_income,
        total_expenses=total_expenses,
        total_pending=total_pending,
        total_paid=total_paid,
        balance=total_income - total_expenses,
        by_category=by_category,
    )
