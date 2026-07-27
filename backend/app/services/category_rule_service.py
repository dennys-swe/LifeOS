from __future__ import annotations

from typing import List, Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.category_rule import CategoryRule
from app.schemas.category_rule import CategoryRuleCreate


def create_rule(db: Session, user_id: UUID, payload: CategoryRuleCreate) -> CategoryRule:
    rule = CategoryRule(
        user_id=user_id,
        keyword=payload.keyword.strip().upper(),
        category_id=payload.category_id,
        priority=payload.priority,
    )
    db.add(rule)
    db.commit()
    db.refresh(rule)
    return rule


def list_rules(db: Session, user_id: UUID) -> List[CategoryRule]:
    result = db.execute(
        select(CategoryRule)
        .where(CategoryRule.user_id == user_id)
        .order_by(CategoryRule.priority.desc(), CategoryRule.keyword.asc())
    )
    return result.scalars().all()


def get_rule(db: Session, user_id: UUID, rule_id: UUID) -> Optional[CategoryRule]:
    return db.execute(
        select(CategoryRule).where(
            CategoryRule.id == rule_id, CategoryRule.user_id == user_id
        )
    ).scalar_one_or_none()


def delete_rule(db: Session, rule: CategoryRule) -> None:
    db.delete(rule)
    db.commit()


def build_keyword_map(db: Session, user_id: UUID) -> dict[str, str]:
    """Returns {KEYWORD_UPPERCASE: str(category_id)} — highest priority keyword wins."""
    rules = list_rules(db, user_id)
    result: dict[str, str] = {}
    for rule in rules:
        if rule.keyword not in result:
            result[rule.keyword] = str(rule.category_id)
    return result
