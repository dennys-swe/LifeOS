from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.users import current_active_user
from app.db.database import get_db
from app.models.user import User
from app.schemas.insight import InsightsResponse
from app.services import insight_service

router = APIRouter(prefix="/insights", tags=["Insights"])


@router.get("", response_model=InsightsResponse)
def get_insights(
    month: int = Query(ge=1, le=12),
    year: int = Query(ge=2000, le=2100),
    db: Session = Depends(get_db),
    user: User = Depends(current_active_user),
):
    return InsightsResponse(
        insights=insight_service.build_insights(db, user.id, month=month, year=year)
    )
