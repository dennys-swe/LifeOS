from __future__ import annotations

from typing import List, Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.category import Category, CategoryKind
from app.models.category_rule import CategoryRule
from app.models.transaction import Transaction, TransactionType
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


def apply_rule_to_existing(db: Session, user_id: UUID, rule: CategoryRule) -> int:
    """Reclassifica os lançamentos já importados que casam com a regra.

    Sem isso a regra só valeria para transação nova: o sync deduplica pelo id da
    Pluggy e pula tudo que já existe, então criar uma regra não mudava nada na
    tela — parecia que não tinha funcionado. Ao criar `CONVENIENCIA -> Mercado`
    havia 66 lançamentos (R$ 576,25) parados em "Transporte".

    A regra é a fonte da verdade e sobrescreve categoria anterior, mas nunca
    cruza a direção do dinheiro: regra de categoria de receita não toca em
    despesa (ver `_category_for_direction`).
    """
    category = db.get(Category, rule.category_id)
    if category is None:
        return 0

    wanted_type = (
        TransactionType.INCOME
        if category.kind == CategoryKind.INCOME
        else TransactionType.EXPENSE
    )

    matched = db.execute(
        select(Transaction).where(
            Transaction.user_id == user_id,
            Transaction.type == wanted_type,
            Transaction.description.ilike(f"%{rule.keyword}%"),
            # `!=` não pegaria os sem categoria: em SQL, NULL != valor é NULL.
            Transaction.category_id.is_distinct_from(rule.category_id),
        )
    ).scalars().all()

    for transaction in matched:
        transaction.category_id = rule.category_id
        db.add(transaction)

    db.commit()
    return len(matched)


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
