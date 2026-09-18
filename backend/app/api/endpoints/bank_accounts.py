from __future__ import annotations

import logging
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
from app.services import bank_sync_service, bill_service
from app.services.reconciliation_service import suggest_pending

router = APIRouter(prefix="/bank-accounts", tags=["Bank Accounts"])

logger = logging.getLogger(__name__)


class ConnectTokenResponse(BaseModel):
    access_token: str


class SyncStartedResponse(BaseModel):
    sync_status: BankAccountSyncStatus


class CardResponse(BaseModel):
    pluggy_account_id: str
    label: str
    ignored: bool


class SyncTriggeredResponse(BaseModel):
    triggered: List[UUID]


@router.post("/connect-token", response_model=ConnectTokenResponse)
def create_connect_token(
    item_id: Optional[UUID] = None,
    user: User = Depends(current_active_user),
):
    try:
        token = bank_sync_service.get_connect_token(item_id=item_id)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return {"access_token": token}


@router.get("/reconciliation-suggestions", response_model=List[ReconciliationSuggestionResponse])
def list_pending_reconciliation_suggestions(
    db: Session = Depends(get_db),
    user: User = Depends(current_active_user),
):
    return suggest_pending(db, user.id)


@router.post(
    "/sync-all", response_model=SyncTriggeredResponse, status_code=status.HTTP_202_ACCEPTED
)
def sync_all_bank_accounts(
    background_tasks: BackgroundTasks,
    force: bool = False,
    db: Session = Depends(get_db),
    user: User = Depends(current_active_user),
):
    """Dispara sync em background pras contas do usuário (issue #114).

    `force=False` (padrão — chamado ao abrir o app): só contas "velhas"
    (`bank_sync_service.is_stale`). `force=True` (botão "Sincronizar tudo"):
    todas, ignorando staleness. Em ambos os casos, `try_start_sync` reivindica
    o lock atomicamente — não empilha sync em cima de outro já em andamento,
    mesmo com duas requisições quase simultâneas (ex: duas abas abertas).

    Todas as contas reivindicadas rodam numa única `BackgroundTasks` que as
    despacha em paralelo (`run_sync_jobs_concurrently`) — agendar um
    `add_task` por conta faria o Starlette rodá-las em sequência, e quem tem
    várias contas ficaria vendo "Atualizando…" pela soma da duração de cada
    uma, não o máximo.
    """
    triggered: List[UUID] = []
    pairs: List[tuple[UUID, UUID]] = []
    for account in bank_sync_service.list_accounts(db, user.id):
        if not account.external_id:
            continue
        if not force and not bank_sync_service.is_stale(account):
            continue
        try:
            # commit=False: commitar a cada conta expiraria (via
            # expire_on_commit) os atributos das contas seguintes ainda não
            # processadas neste mesmo loop, forçando um SELECT implícito
            # extra por conta. `db.begin_nested()` isola cada tentativa no
            # seu próprio savepoint — uma falha transitória numa conta não
            # pode desfazer o claim (ainda não commitado) de uma conta
            # anterior já reivindicada com sucesso neste mesmo loop (mesmo
            # cuidado que `daily_sync.run` tem pro laço equivalente).
            with db.begin_nested():
                won = bank_sync_service.try_start_sync(db, account, commit=False)
        except Exception:
            # Isolada por conta: uma falha transitória numa conta não pode
            # devolver 500 pro request inteiro e deixar de disparar sync pras
            # outras contas do usuário que estavam bem.
            logger.exception("falha ao reivindicar lock de sync (account=%s)", account.id)
            continue
        if not won:
            continue
        pairs.append((account.id, user.id))
        triggered.append(account.id)
    db.commit()
    if pairs:
        background_tasks.add_task(bank_sync_service.run_sync_jobs_concurrently, pairs)
    return SyncTriggeredResponse(triggered=triggered)


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


@router.post(
    "/{account_id}/sync", response_model=SyncStartedResponse, status_code=status.HTTP_202_ACCEPTED
)
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
        raise HTTPException(
            status_code=400, detail="Conta sem item_id da Pluggy. Conecte o banco primeiro."
        )
    if not bank_sync_service.try_start_sync(db, account):
        return SyncStartedResponse(sync_status=account.sync_status)

    background_tasks.add_task(bank_sync_service.run_sync_job, account.id, user.id)
    return SyncStartedResponse(sync_status=account.sync_status)


@router.get("/{account_id}/cards", response_model=List[CardResponse])
def list_account_cards(
    account_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(current_active_user),
):
    account = bank_sync_service.get_account(db, user.id, account_id)
    if account is None:
        raise HTTPException(status_code=404, detail="Bank account not found")
    return bill_service.list_cards(db, user.id, account_id)


@router.post(
    "/{account_id}/cards/{pluggy_account_id}/ignore", status_code=status.HTTP_204_NO_CONTENT
)
def ignore_account_card(
    account_id: UUID,
    pluggy_account_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(current_active_user),
):
    account = bank_sync_service.get_account(db, user.id, account_id)
    if account is None:
        raise HTTPException(status_code=404, detail="Bank account not found")
    try:
        bill_service.ignore_card(db, user.id, account_id, pluggy_account_id)
    except bill_service.CardNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Card not found on this account") from exc
    return None


@router.delete(
    "/{account_id}/cards/{pluggy_account_id}/ignore", status_code=status.HTTP_204_NO_CONTENT
)
def unignore_account_card(
    account_id: UUID,
    pluggy_account_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(current_active_user),
):
    account = bank_sync_service.get_account(db, user.id, account_id)
    if account is None:
        raise HTTPException(status_code=404, detail="Bank account not found")
    bill_service.unignore_card(db, user.id, account_id, pluggy_account_id)
    return None
