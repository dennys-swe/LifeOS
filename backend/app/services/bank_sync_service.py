from __future__ import annotations

import json
from datetime import date as date_type
from datetime import datetime, timezone
from decimal import Decimal
from typing import List, Optional
from uuid import UUID

import pluggy_sdk
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.database import SessionLocal
from app.models.bank_account import BankAccount, BankAccountSyncStatus
from app.models.transaction import Transaction, TransactionType
from app.schemas.bank_account import BankAccountCreate
from app.services import bill_service
from app.services.category_rule_service import build_keyword_map
from app.services.pluggy_client import get_api_client
from app.services.reconciliation_service import (
    auto_reconcile_confident_matches,
    drop_resolved_payables,
    suggest_reconciliation,
)


def list_accounts(db: Session, user_id: UUID) -> List[BankAccount]:
    return db.execute(
        select(BankAccount).where(BankAccount.user_id == user_id).order_by(BankAccount.name.asc())
    ).scalars().all()


def get_account(db: Session, user_id: UUID, account_id: UUID) -> Optional[BankAccount]:
    return db.execute(
        select(BankAccount).where(
            BankAccount.id == account_id, BankAccount.user_id == user_id
        )
    ).scalar_one_or_none()


def create_account(db: Session, user_id: UUID, payload: BankAccountCreate) -> BankAccount:
    account = BankAccount(user_id=user_id, **payload.model_dump())
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


def _parse_pluggy_date(date_str: str) -> date_type:
    return datetime.fromisoformat(date_str.replace("Z", "+00:00")).date()


def sync_account(db: Session, account: BankAccount) -> dict:
    if not account.external_id:
        raise ValueError("Conta sem item_id da Pluggy. Conecte o banco primeiro.")

    item_id = UUID(account.external_id)
    imported = 0
    skipped = 0
    bills_synced = 0
    new_transactions: List[Transaction] = []
    keyword_map = build_keyword_map(db, account.user_id)

    with get_api_client() as ac:
        account_api = pluggy_sdk.AccountApi(ac)
        tx_api = pluggy_sdk.TransactionApi(ac)
        bill_api = pluggy_sdk.BillApi(ac)

        pluggy_accounts = account_api.accounts_list(item_id=item_id).results or []

        for pluggy_acct in pluggy_accounts:
            if getattr(pluggy_acct, "type", None) == "CREDIT":
                card_name = getattr(pluggy_acct, "marketing_name", None) or getattr(pluggy_acct, "name", None)
                try:
                    # Mesmo workaround do sync de transações: bypass da validação
                    # Pydantic do SDK usando o JSON bruto.
                    raw_bills = bill_api.bills_list_without_preload_content(
                        account_id=pluggy_acct.id
                    )
                    bills_data = json.loads(raw_bills.data).get("results") or []
                except Exception:
                    # Bills só existem em conexões Open Finance Regulado — degrada
                    # silenciosamente quando a conexão não as suporta.
                    bills_data = []

                for bill_data in bills_data:
                    bill_service.upsert_bill(
                        db, account.user_id, account, pluggy_acct.id, bill_data, card_name=card_name
                    )
                    bills_synced += 1

            page = 1
            while True:
                # Use without_preload_content + raw JSON to bypass Pluggy SDK Pydantic
                # validation errors caused by type mismatches in nested models
                # (e.g. CreditCardMetadata.payeeMCC returned as int, declared as StrictStr).
                raw_resp = tx_api.transactions_list_without_preload_content(
                    account_id=pluggy_acct.id,
                    page=page,
                    page_size=500,
                )
                page_data = json.loads(raw_resp.data)
                transactions = page_data.get("results") or []
                total_pages = page_data.get("totalPages") or 1

                if not transactions:
                    break

                for tx in transactions:
                    source_key = f"pluggy:{tx['id']}"
                    exists = db.execute(
                        select(Transaction).where(
                            Transaction.user_id == account.user_id,
                            Transaction.source == source_key,
                        )
                    ).scalar_one_or_none()

                    if exists:
                        skipped += 1
                        continue

                    amount_raw = tx.get("amount", 0) or 0
                    tx_type = (
                        TransactionType.INCOME
                        if amount_raw > 0
                        else TransactionType.EXPENSE
                    )
                    tx_date = _parse_pluggy_date(tx["date"]) if tx.get("date") else date_type.today()
                    description = (tx.get("description") or "")[:255]
                    normalized = description.upper()
                    category_id = None
                    for keyword, mapped_id in keyword_map.items():
                        if keyword in normalized:
                            category_id = UUID(mapped_id)
                            break
                    new_tx = Transaction(
                        user_id=account.user_id,
                        date=tx_date,
                        description=description,
                        amount=Decimal(str(abs(amount_raw))),
                        type=tx_type,
                        source=source_key,
                        category_id=category_id,
                    )
                    db.add(new_tx)
                    new_transactions.append(new_tx)
                    imported += 1

                if page >= total_pages:
                    break
                page += 1

    account.last_sync_at = datetime.now(timezone.utc)
    db.commit()
    for tx in new_transactions:
        db.refresh(tx)

    suggestions = suggest_reconciliation(db, account.user_id, new_transactions)
    auto_confirmed = auto_reconcile_confident_matches(db, account.user_id, suggestions)
    remaining_suggestions = drop_resolved_payables(suggestions, auto_confirmed)

    return {
        "imported": imported,
        "skipped": skipped,
        "bills_synced": bills_synced,
        "auto_reconciled": len(auto_confirmed),
        "suggestions": remaining_suggestions,
    }


def start_sync(db: Session, account: BankAccount) -> None:
    """Marca a conta como 'sincronizando' — chamado na request antes de agendar o job em background."""
    account.sync_status = BankAccountSyncStatus.SYNCING
    account.last_sync_error = None
    db.add(account)
    db.commit()


def run_sync_job(account_id: UUID, user_id: UUID) -> None:
    """Job de background: roda fora do ciclo de vida da request, então abre sua própria sessão."""
    db = SessionLocal()
    try:
        account = get_account(db, user_id, account_id)
        if account is None:
            return
        try:
            sync_account(db, account)
            account.sync_status = BankAccountSyncStatus.IDLE
            account.last_sync_error = None
            db.add(account)
            db.commit()
        except Exception as exc:
            db.rollback()
            account = get_account(db, user_id, account_id)
            if account is not None:
                account.sync_status = BankAccountSyncStatus.ERROR
                account.last_sync_error = str(exc)
                db.add(account)
                db.commit()
    finally:
        db.close()
