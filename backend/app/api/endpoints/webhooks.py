from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Request, status
from sqlalchemy import select

from app.models.bank_account import BankAccount, BankAccountSyncStatus
from app.services import bank_sync_service

router = APIRouter(prefix="/webhooks", tags=["Webhooks"])

# Eventos que indicam que há dado novo pra puxar da Pluggy pra essa conexão.
_SYNC_TRIGGER_EVENTS = {
    "item/created",
    "item/updated",
    "transactions/created",
    "transactions/updated",
}


@router.post("/pluggy", status_code=status.HTTP_200_OK)
async def pluggy_webhook(request: Request, background_tasks: BackgroundTasks):
    """Recebe eventos da Pluggy e dispara o sync em background da conta afetada.

    Sem autenticação por header: é um endpoint público (a Pluggy não injeta
    nossas credenciais de app aqui). O impacto de uma chamada forjada é, no
    pior caso, disparar um sync — uma operação de leitura idempotente — então
    o risco é aceitável sem verificação de assinatura.
    """
    payload = await request.json()
    event = payload.get("event")
    item_id = payload.get("itemId")

    if event in _SYNC_TRIGGER_EVENTS and item_id:
        db = bank_sync_service.SessionLocal()
        try:
            account = db.execute(
                select(BankAccount).where(BankAccount.external_id == item_id)
            ).scalar_one_or_none()
            if account is not None and account.sync_status != BankAccountSyncStatus.SYNCING:
                bank_sync_service.start_sync(db, account)
                background_tasks.add_task(bank_sync_service.run_sync_job, account.id, account.user_id)
        finally:
            db.close()

    return {"received": True}
