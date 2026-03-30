from __future__ import annotations

from calendar import monthrange
from datetime import date
from typing import Iterable, List, Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.transaction import Transaction, TransactionType
from app.schemas.transaction import TransactionCreate


def create_transactions(db: Session, payloads: Iterable[TransactionCreate]) -> List[Transaction]:
    items = [Transaction(**payload.model_dump()) for payload in payloads]
    if not items:
        return []
    db.add_all(items)
    db.commit()
    for item in items:
        db.refresh(item)
    return items


def create_transaction(db: Session, payload: TransactionCreate) -> Transaction:
    item = Transaction(**payload.model_dump())
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


def get_transactions(
    db: Session,
    tx_type: Optional[TransactionType] = None,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    month: Optional[int] = None,
    year: Optional[int] = None,
) -> List[Transaction]:
    query = select(Transaction)

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

    query = query.order_by(Transaction.date.desc())
    result = db.execute(query)
    return result.scalars().all()


def get_transaction(db: Session, transaction_id: UUID) -> Optional[Transaction]:
    return db.get(Transaction, transaction_id)


def delete_transaction(db: Session, transaction: Transaction) -> None:
    db.delete(transaction)
    db.commit()
