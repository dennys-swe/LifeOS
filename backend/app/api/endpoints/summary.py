from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.schemas.summary import HistoryResponse, SummaryResponse
from app.services import summary_service

router = APIRouter(prefix="/summary", tags=["Summary"])


@router.get("/history", response_model=HistoryResponse)
def get_history(
    months: int = Query(default=6, ge=1, le=24),
    db: Session = Depends(get_db),
):
    return summary_service.get_history(db, months=months)


@router.get("", response_model=SummaryResponse)
def get_summary(
    month: int = Query(ge=1, le=12),
    year: int = Query(ge=2000, le=2100),
    db: Session = Depends(get_db),
):
    return summary_service.get_summary(db, month=month, year=year)
