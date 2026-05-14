from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.schemas.push_subscription import PushSubscriptionCreate, PushSubscriptionResponse
from app.services import push_service

router = APIRouter(prefix="/push-subscriptions", tags=["Push Notifications"])


@router.post("", response_model=PushSubscriptionResponse, status_code=status.HTTP_201_CREATED)
def subscribe(payload: PushSubscriptionCreate, db: Session = Depends(get_db)):
    return push_service.save_subscription(db, payload)


@router.post("/notify", status_code=status.HTTP_200_OK)
def trigger_notifications(days: int = 3, db: Session = Depends(get_db)):
    try:
        sent = push_service.send_upcoming_notifications(db, days=days)
        return {"sent": sent}
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
