from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.database import get_db
from app.jobs.daily_sync import run as run_daily_sync

router = APIRouter(prefix="/jobs", tags=["Jobs"])

logger = logging.getLogger(__name__)


def _require_cron_secret(x_cron_secret: Optional[str]) -> None:
    if not settings.cron_secret or x_cron_secret != settings.cron_secret:
        raise HTTPException(status_code=403, detail="Invalid or missing X-Cron-Secret header")


@router.post("/daily-sync", status_code=status.HTTP_200_OK)
def trigger_daily_sync(
    db: Session = Depends(get_db),
    x_cron_secret: Optional[str] = Header(default=None),
):
    _require_cron_secret(x_cron_secret)
    return run_daily_sync(db)


@router.post("/verify-sentry", status_code=status.HTTP_200_OK)
def verify_sentry(x_cron_secret: Optional[str] = Header(default=None)):
    """Dispara um erro controlado para confirmar que o Sentry está recebendo eventos.

    Temporário — remover depois de validar em produção (ver #3). Protegido pelo
    mesmo X-Cron-Secret do daily-sync. Usa `logger.error`, o mesmo caminho das
    falhas degradadas do sync, então valida a integração de logging do SDK.
    """
    _require_cron_secret(x_cron_secret)
    if not settings.sentry_dsn:
        raise HTTPException(status_code=503, detail="SENTRY_DSN não configurado")
    logger.error("verify-sentry: evento de teste da integração LifeOS <> Sentry")
    return {"status": "evento enviado ao Sentry"}
