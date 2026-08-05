from __future__ import annotations

from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.users import current_active_user
from app.db.database import get_db
from app.models.user import User
from app.schemas.category_rule import CategoryRuleCreate, CategoryRuleResponse
from app.services import category_rule_service

router = APIRouter(prefix="/category-rules", tags=["Category Rules"])


@router.get("", response_model=List[CategoryRuleResponse])
def list_category_rules(
    db: Session = Depends(get_db),
    user: User = Depends(current_active_user),
):
    return category_rule_service.list_rules(db, user.id)


@router.post("", response_model=CategoryRuleResponse, status_code=status.HTTP_201_CREATED)
def create_category_rule(
    payload: CategoryRuleCreate,
    db: Session = Depends(get_db),
    user: User = Depends(current_active_user),
):
    rule = category_rule_service.create_rule(db, user.id, payload)
    # A regra vale desde já para o histórico: o sync pula transação existente,
    # então sem isso ela só afetaria importações futuras.
    applied = category_rule_service.apply_rule_to_existing(db, user.id, rule)
    return CategoryRuleResponse.model_validate(rule).model_copy(
        update={"applied_count": applied}
    )


@router.delete("/{rule_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_category_rule(
    rule_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(current_active_user),
):
    rule = category_rule_service.get_rule(db, user.id, rule_id)
    if rule is None:
        raise HTTPException(status_code=404, detail="Category rule not found")
    category_rule_service.delete_rule(db, rule)
    return None
