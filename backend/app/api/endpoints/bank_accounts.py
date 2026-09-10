from __future__ import annotations

from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.users import current_active_user
from app.db.database import get_db
from app.models.bank_account import BankAccountSyncStatus
from app.models.user import User
from app.schemas.bank_account import BankAccountCreate, BankAccountResponse, BankAccountUpdate
from app.schemas.reconciliation import ReconciliationSuggestionResponse
from app.services import bank_sync_service
from app.services.reconciliation_service import suggest_pending

router = APIRouter(prefix="/bank-accounts", tags=["Bank Accounts"])


class ConnectTokenResponse(BaseModel):
    access_token: str


class SyncStartedResponse(BaseModel):
    sync_status: BankAccountSyncStatus


@router.post("/connect-token", response_model=ConnectTokenResponse)
def create_connect_token(
    item_id: Optional[UUID] = None,
    user: User = Depends(current_active_user),
):
    try:
        token = bank_sync_service.get_connect_token(item_id=item_id)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    return {"access_token": token}


@router.get("/reconciliation-suggestions", response_model=List[ReconciliationSuggestionResponse])
def list_pending_reconciliation_suggestions(
    db: Session = Depends(get_db),
    user: User = Depends(current_active_user),
):
    return suggest_pending(db, user.id)


@router.get("", response_model=List[BankAccountResponse])
def list_bank_accounts(
    db: Session = Depends(get_db),
    user: User = Depends(current_active_user),
):
    return bank_sync_service.list_accounts(db, user.id)


@router.post("", response_model=BankAccountResponse, status_code=status.HTTP_201_CREATED)
def create_bank_account(
    payload: BankAccountCreate,
    db: Session = Depends(get_db),
    user: User = Depends(current_active_user),
):
    return bank_sync_service.create_account(db, user.id, payload)


@router.patch("/{account_id}", response_model=BankAccountResponse)
def update_bank_account(
    account_id: UUID,
    payload: BankAccountUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(current_active_user),
):
    account = bank_sync_service.get_account(db, user.id, account_id)
    if account is None:
        raise HTTPException(status_code=404, detail="Bank account not found")
    return bank_sync_service.update_account(db, account, payload)


@router.delete("/{account_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_bank_account(
    account_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(current_active_user),
):
    account = bank_sync_service.get_account(db, user.id, account_id)
    if account is None:
        raise HTTPException(status_code=404, detail="Bank account not found")
    bank_sync_service.delete_account(db, account)
    return None


@router.post("/{account_id}/sync", response_model=SyncStartedResponse, status_code=status.HTTP_202_ACCEPTED)
def sync_bank_account(
    account_id: UUID,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    user: User = Depends(current_active_user),
):
    account = bank_sync_service.get_account(db, user.id, account_id)
    if account is None:
        raise HTTPException(status_code=404, detail="Bank account not found")
    if not account.external_id:
        raise HTTPException(status_code=400, detail="Conta sem item_id da Pluggy. Conecte o banco primeiro.")
    if not bank_sync_service.can_start_sync(account):
        return SyncStartedResponse(sync_status=account.sync_status)

    bank_sync_service.start_sync(db, account)
    background_tasks.add_task(bank_sync_service.run_sync_job, account.id, user.id)
    return SyncStartedResponse(sync_status=account.sync_status)
