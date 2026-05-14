from __future__ import annotations

from typing import List, Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.bank_account import BankAccount
from app.schemas.bank_account import BankAccountCreate


def list_accounts(db: Session) -> List[BankAccount]:
    return db.execute(select(BankAccount).order_by(BankAccount.name.asc())).scalars().all()


def get_account(db: Session, account_id: UUID) -> Optional[BankAccount]:
    return db.get(BankAccount, account_id)


def create_account(db: Session, payload: BankAccountCreate) -> BankAccount:
    account = BankAccount(**payload.model_dump())
    db.add(account)
    db.commit()
    db.refresh(account)
    return account


def delete_account(db: Session, account: BankAccount) -> None:
    db.delete(account)
    db.commit()


def sync_account(db: Session, account_id: UUID) -> None:
    """Pluggy/Open Finance integration — not yet implemented."""
    raise NotImplementedError(
        "Bank sync not yet configured. Pluggy/Open Finance integration is planned for a future release."
    )
