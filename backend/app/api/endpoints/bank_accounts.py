from __future__ import annotations

from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.schemas.bank_account import BankAccountCreate, BankAccountResponse
from app.services import bank_sync_service

router = APIRouter(prefix="/bank-accounts", tags=["Bank Accounts"])


@router.get("", response_model=List[BankAccountResponse])
def list_bank_accounts(db: Session = Depends(get_db)):
    return bank_sync_service.list_accounts(db)


@router.post("", response_model=BankAccountResponse, status_code=status.HTTP_201_CREATED)
def create_bank_account(payload: BankAccountCreate, db: Session = Depends(get_db)):
    return bank_sync_service.create_account(db, payload)


@router.delete("/{account_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_bank_account(account_id: UUID, db: Session = Depends(get_db)):
    account = bank_sync_service.get_account(db, account_id)
    if account is None:
        raise HTTPException(status_code=404, detail="Bank account not found")
    bank_sync_service.delete_account(db, account)
    return None


@router.post("/{account_id}/sync", status_code=status.HTTP_501_NOT_IMPLEMENTED)
def sync_bank_account(account_id: UUID, db: Session = Depends(get_db)):
    account = bank_sync_service.get_account(db, account_id)
    if account is None:
        raise HTTPException(status_code=404, detail="Bank account not found")
    return {
        "detail": "Bank sync not yet configured. Pluggy/Open Finance integration is planned for a future release.",
        "account_id": str(account_id),
    }
