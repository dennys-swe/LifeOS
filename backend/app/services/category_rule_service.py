from __future__ import annotations

from typing import List, Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.category_rule import CategoryRule
from app.schemas.category_rule import CategoryRuleCreate


def create_rule(db: Session, payload: CategoryRuleCreate) -> CategoryRule:
    rule = CategoryRule(
        keyword=payload.keyword.strip().upper(),
        category_id=payload.category_id,
        priority=payload.priority,
    )
    db.add(rule)
    db.commit()
    db.refresh(rule)
    return rule


def list_rules(db: Session) -> List[CategoryRule]:
    result = db.execute(
        select(CategoryRule).order_by(CategoryRule.priority.desc(), CategoryRule.keyword.asc())
    )
    return result.scalars().all()


def get_rule(db: Session, rule_id: UUID) -> Optional[CategoryRule]:
    return db.get(CategoryRule, rule_id)


def delete_rule(db: Session, rule: CategoryRule) -> None:
    db.delete(rule)
    db.commit()


def build_keyword_map(db: Session) -> dict[str, str]:
    """Returns {KEYWORD_UPPERCASE: str(category_id)} — highest priority keyword wins."""
    rules = list_rules(db)
    result: dict[str, str] = {}
    for rule in rules:
        if rule.keyword not in result:
            result[rule.keyword] = str(rule.category_id)
    return result
