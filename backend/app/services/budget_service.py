from __future__ import annotations

from decimal import Decimal
from typing import List, Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.budget import Budget
from app.schemas.budget import BudgetCreate


def list_budgets(db: Session, user_id: UUID, month: int, year: int) -> List[Budget]:
    result = db.execute(
        select(Budget).where(
            Budget.user_id == user_id, Budget.month == month, Budget.year == year
        )
    )
    return result.scalars().all()


def get_budget(db: Session, user_id: UUID, budget_id: UUID) -> Optional[Budget]:
    return db.execute(
        select(Budget).where(Budget.id == budget_id, Budget.user_id == user_id)
    ).scalar_one_or_none()


def get_budget_for_category(
    db: Session, user_id: UUID, category_id: UUID, month: int, year: int
) -> Optional[Budget]:
    return db.execute(
        select(Budget).where(
            Budget.user_id == user_id,
            Budget.category_id == category_id,
            Budget.month == month,
            Budget.year == year,
        )
    ).scalar_one_or_none()


def create_or_update_budget(db: Session, user_id: UUID, payload: BudgetCreate) -> Budget:
    existing = get_budget_for_category(
        db, user_id, payload.category_id, payload.month, payload.year
    )
    if existing:
        existing.limit_amount = payload.limit_amount
        db.add(existing)
        db.commit()
        db.refresh(existing)
        return existing

    budget = Budget(user_id=user_id, **payload.model_dump())
    db.add(budget)
    db.commit()
    db.refresh(budget)
    return budget


def delete_budget(db: Session, budget: Budget) -> None:
    db.delete(budget)
    db.commit()


def build_budget_map(db: Session, user_id: UUID, month: int, year: int) -> dict[UUID, Decimal]:
    """Returns {category_id: limit_amount} for the given user/month/year."""
    budgets = list_budgets(db, user_id, month, year)
    return {b.category_id: Decimal(str(b.limit_amount)) for b in budgets}
