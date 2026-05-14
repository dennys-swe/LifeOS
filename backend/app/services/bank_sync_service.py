from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import List, Optional
from uuid import UUID

import pluggy_sdk
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.bank_account import BankAccount
from app.models.transaction import Transaction, TransactionType
from app.schemas.bank_account import BankAccountCreate
from app.services.pluggy_client import get_api_client


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


def get_connect_token(item_id: Optional[UUID] = None) -> str:
    with get_api_client() as ac:
        auth_api = pluggy_sdk.AuthApi(ac)
        payload = pluggy_sdk.ConnectTokenRequest(itemId=item_id) if item_id else None
        resp = auth_api.connect_token_create(connect_token_request=payload)
    return resp.access_token


def sync_account(db: Session, account: BankAccount) -> dict:
    if not account.external_id:
        raise ValueError("Conta sem item_id da Pluggy. Conecte o banco primeiro.")

    item_id = UUID(account.external_id)
    imported = 0
    skipped = 0

    with get_api_client() as ac:
        account_api = pluggy_sdk.AccountApi(ac)
        tx_api = pluggy_sdk.TransactionApi(ac)

        pluggy_accounts = account_api.accounts_list(item_id=item_id).results or []

        for pluggy_acct in pluggy_accounts:
            page = 1
            while True:
                page_resp = tx_api.transactions_list(
                    account_id=pluggy_acct.id,
                    page=page,
                    page_size=500,
                )
                transactions = page_resp.results or []
                if not transactions:
                    break

                for tx in transactions:
                    source_key = f"pluggy:{tx.id}"
                    exists = db.execute(
                        select(Transaction).where(Transaction.source == source_key)
                    ).scalar_one_or_none()

                    if exists:
                        skipped += 1
                        continue

                    tx_type = (
                        TransactionType.INCOME
                        if tx.amount > 0
                        else TransactionType.EXPENSE
                    )
                    new_tx = Transaction(
                        date=tx.date.date() if isinstance(tx.date, datetime) else tx.date,
                        description=tx.description[:255],
                        amount=Decimal(str(abs(tx.amount))),
                        type=tx_type,
                        source=source_key,
                    )
                    db.add(new_tx)
                    imported += 1

                if page >= (page_resp.total_pages or 1):
                    break
                page += 1

    account.last_sync_at = datetime.now(timezone.utc)
    db.commit()

    return {"imported": imported, "skipped": skipped}
