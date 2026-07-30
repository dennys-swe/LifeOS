from __future__ import annotations

from calendar import monthrange
from datetime import date
from typing import List, Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.transaction import Transaction, TransactionType
from app.schemas.transaction import TransactionCreate


def create_transaction(db: Session, user_id: UUID, payload: TransactionCreate) -> Transaction:
    item = Transaction(user_id=user_id, **payload.model_dump())
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


def get_transactions(
    db: Session,
    user_id: UUID,
    tx_type: Optional[TransactionType] = None,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    month: Optional[int] = None,
    year: Optional[int] = None,
    category_id: Optional[UUID] = None,
    uncategorized: bool = False,
    include_transfers: bool = True,
    limit: Optional[int] = None,
    offset: int = 0,
) -> List[Transaction]:
    """`include_transfers=False` casa com a definição de gasto do `/summary`.

    `uncategorized=True` filtra `category_id IS NULL` — necessário porque o
    drill-down da linha "Sem categoria" do dashboard não tem UUID para passar.
    """
    query = select(Transaction).where(Transaction.user_id == user_id)

    if month is not None and year is not None:
        start_date = date(year, month, 1)
        end_day = monthrange(year, month)[1]
        end_date = date(year, month, end_day)

    if tx_type is not None:
        query = query.where(Transaction.type == tx_type)
    if start_date is not None:
        query = query.where(Transaction.date >= start_date)
    if end_date is not None:
        query = query.where(Transaction.date <= end_date)
    if uncategorized:
        query = query.where(Transaction.category_id.is_(None))
    elif category_id is not None:
        query = query.where(Transaction.category_id == category_id)
    if not include_transfers:
        query = query.where(Transaction.is_transfer.is_(False))

    # `id` desempata: sem um critério estável, duas transações do mesmo dia
    # podem trocar de lugar entre páginas e sumir da paginação.
    query = query.order_by(Transaction.date.desc(), Transaction.id.desc())

    if offset:
        query = query.offset(offset)
    if limit is not None:
        query = query.limit(limit)

    result = db.execute(query)
    return result.scalars().all()


def get_transaction(db: Session, user_id: UUID, transaction_id: UUID) -> Optional[Transaction]:
    return db.execute(
        select(Transaction).where(
            Transaction.id == transaction_id, Transaction.user_id == user_id
        )
    ).scalar_one_or_none()


def delete_transaction(db: Session, transaction: Transaction) -> None:
    db.delete(transaction)
    db.commit()
