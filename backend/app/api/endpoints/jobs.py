from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.database import get_db
from app.jobs.daily_sync import run as run_daily_sync

router = APIRouter(prefix="/jobs", tags=["Jobs"])


@router.post("/daily-sync", status_code=status.HTTP_200_OK)
def trigger_daily_sync(
    db: Session = Depends(get_db),
    x_cron_secret: Optional[str] = Header(default=None),
):
    if not settings.cron_secret or x_cron_secret != settings.cron_secret:
        raise HTTPException(status_code=403, detail="Invalid or missing X-Cron-Secret header")
    return run_daily_sync(db)
