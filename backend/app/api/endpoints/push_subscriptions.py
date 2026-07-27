from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.users import current_active_user
from app.db.database import get_db
from app.models.user import User
from app.schemas.push_subscription import PushSubscriptionCreate, PushSubscriptionResponse
from app.services import push_service

router = APIRouter(prefix="/push-subscriptions", tags=["Push Notifications"])


@router.get("/vapid-public-key")
def get_vapid_public_key(user: User = Depends(current_active_user)):
    if not settings.vapid_public_key:
        raise HTTPException(status_code=503, detail="VAPID_PUBLIC_KEY not configured.")
    return {"public_key": settings.vapid_public_key}


@router.post("", response_model=PushSubscriptionResponse, status_code=status.HTTP_201_CREATED)
def subscribe(
    payload: PushSubscriptionCreate,
    db: Session = Depends(get_db),
    user: User = Depends(current_active_user),
):
    return push_service.save_subscription(db, user.id, payload)


@router.post("/notify", status_code=status.HTTP_200_OK)
def trigger_notifications(
    days: int = 3,
    db: Session = Depends(get_db),
    user: User = Depends(current_active_user),
):
    try:
        sent = push_service.send_upcoming_notifications(db, user.id, days=days)
        return {"sent": sent}
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
