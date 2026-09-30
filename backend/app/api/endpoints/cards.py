from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.users import current_active_user
from app.db.database import get_db
from app.models.user import User
from app.schemas.card_limit import CardLimitsResponse
from app.services import card_limit_service

router = APIRouter(prefix="/cards", tags=["Cards"])


@router.get("/limits", response_model=CardLimitsResponse)
def get_card_limits(
    db: Session = Depends(get_db),
    user: User = Depends(current_active_user),
):
    """Limite total, usado, disponível e % usado dos cartões (#204)."""
    return card_limit_service.get_card_limits(db, user.id)
