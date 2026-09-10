from __future__ import annotations

import logging

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request, status
from sqlalchemy import select

from app.core.config import settings
from app.models.bank_account import BankAccount
from app.services import bank_sync_service

router = APIRouter(prefix="/webhooks", tags=["Webhooks"])

logger = logging.getLogger(__name__)

# Eventos que indicam que há dado novo pra puxar da Pluggy pra essa conexão.
_SYNC_TRIGGER_EVENTS = {
    "item/created",
    "item/updated",
    "transactions/created",
    "transactions/updated",
}


async def _process_pluggy_event(request: Request, background_tasks: BackgroundTasks) -> dict:
    """Dispara o sync em background da conta afetada pelo evento.

    O impacto máximo de uma chamada forjada é disparar um sync (leitura
    idempotente), e o `sync_status != SYNCING` evita empilhar. Ainda assim,
    quando `PLUGGY_WEBHOOK_SECRET` está setado a URL vira
    `POST /webhooks/pluggy/<secret>` e o path sem segredo para de agir — a
    Pluggy não injeta credenciais aqui, então o segredo no path é a trava.
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
            if account is not None and bank_sync_service.can_start_sync(account):
                bank_sync_service.start_sync(db, account)
                background_tasks.add_task(
                    bank_sync_service.run_sync_job, account.id, account.user_id
                )
        finally:
            db.close()

    return {"received": True}


@router.post("/pluggy", status_code=status.HTTP_200_OK)
async def pluggy_webhook(request: Request, background_tasks: BackgroundTasks):
    if settings.pluggy_webhook_secret:
        # Segredo configurado: a URL registrada na Pluggy deve carregá-lo no
        # path. Um POST aqui é tráfego velho ou forjado — responde 200 (a Pluggy
        # não deve reencaminhar por causa de erro) mas não faz nada.
        logger.warning(
            "POST /webhooks/pluggy sem segredo no path — atualize a webhook URL "
            "no dashboard da Pluggy para /webhooks/pluggy/<PLUGGY_WEBHOOK_SECRET>"
        )
        return {"received": True, "ignored": "missing path secret"}
    return await _process_pluggy_event(request, background_tasks)


@router.post("/pluggy/{secret}", status_code=status.HTTP_200_OK)
async def pluggy_webhook_with_secret(
    secret: str, request: Request, background_tasks: BackgroundTasks
):
    if settings.pluggy_webhook_secret and secret != settings.pluggy_webhook_secret:
        raise HTTPException(status_code=403, detail="Invalid webhook secret")
    return await _process_pluggy_event(request, background_tasks)
