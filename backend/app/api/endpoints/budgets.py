from __future__ import annotations

from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.users import current_active_user
from app.db.database import get_db
from app.models.user import User
from app.schemas.budget import BudgetCreate, BudgetResponse
from app.services import budget_service

router = APIRouter(prefix="/budgets", tags=["Budgets"])


@router.get("", response_model=List[BudgetResponse])
def list_budgets(
    month: int = Query(ge=1, le=12),
    year: int = Query(ge=2000, le=2100),
    db: Session = Depends(get_db),
    user: User = Depends(current_active_user),
):
    return budget_service.list_budgets(db, user.id, month=month, year=year)


@router.post("", response_model=BudgetResponse, status_code=status.HTTP_200_OK)
def upsert_budget(
    payload: BudgetCreate,
    db: Session = Depends(get_db),
    user: User = Depends(current_active_user),
):
    return budget_service.create_or_update_budget(db, user.id, payload)


@router.delete("/{budget_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_budget(
    budget_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(current_active_user),
):
    budget = budget_service.get_budget(db, user.id, budget_id)
    if budget is None:
        raise HTTPException(status_code=404, detail="Budget not found")
    budget_service.delete_budget(db, budget)
    return None
