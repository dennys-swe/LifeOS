from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional
from uuid import UUID

from sqlalchemy import or_, select
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
        is_transfer=payload.is_transfer,
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
        TransactionType.INCOME if category.kind == CategoryKind.INCOME else TransactionType.EXPENSE
    )

    # Sem `rule.is_transfer`, só interessa quem muda de categoria (como sempre
    # foi). Com `rule.is_transfer`, também precisa pegar quem já está na
    # categoria certa mas ainda não está marcado como transferência — senão
    # uma transação que a Pluggy já tinha jogado em "Outras receitas" (mesma
    # categoria da regra) nunca seria selecionada, e `is_transfer` nunca
    # ligaria pra ela (exatamente o caso de uso da divisão de contas).
    needs_update = (
        or_(
            Transaction.category_id.is_distinct_from(rule.category_id),
            Transaction.is_transfer.is_(False),
        )
        if rule.is_transfer
        # `!=` não pegaria os sem categoria: em SQL, NULL != valor é NULL.
        else Transaction.category_id.is_distinct_from(rule.category_id)
    )

    matched = (
        db.execute(
            select(Transaction).where(
                Transaction.user_id == user_id,
                Transaction.type == wanted_type,
                Transaction.description.ilike(f"%{rule.keyword}%"),
                needs_update,
            )
        )
        .scalars()
        .all()
    )

    for transaction in matched:
        transaction.category_id = rule.category_id
        # Só liga is_transfer, nunca desliga: a regra pode reconhecer um caso
        # a mais (ex: pessoa específica) que `pluggy_category_map` não sabe,
        # mas não deve desfazer uma transferência que a Pluggy já identificou
        # certo por outro motivo.
        if rule.is_transfer:
            transaction.is_transfer = True
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
        select(CategoryRule).where(CategoryRule.id == rule_id, CategoryRule.user_id == user_id)
    ).scalar_one_or_none()


def delete_rule(db: Session, rule: CategoryRule) -> None:
    db.delete(rule)
    db.commit()


@dataclass(frozen=True)
class KeywordRule:
    category_id: str
    is_transfer: bool


def build_keyword_map(db: Session, user_id: UUID) -> dict[str, KeywordRule]:
    """Returns {KEYWORD_UPPERCASE: KeywordRule(category_id, is_transfer)} —
    highest priority keyword wins."""
    rules = list_rules(db, user_id)
    result: dict[str, KeywordRule] = {}
    for rule in rules:
        if rule.keyword not in result:
            result[rule.keyword] = KeywordRule(str(rule.category_id), rule.is_transfer)
    return result
