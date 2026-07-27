from __future__ import annotations

import json
from datetime import date, timedelta
from typing import List
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.payable import Payable, PayableStatus
from app.models.push_subscription import PushSubscription
from app.schemas.push_subscription import PushSubscriptionCreate


def save_subscription(
    db: Session, user_id: UUID, payload: PushSubscriptionCreate
) -> PushSubscription:
    existing = db.execute(
        select(PushSubscription).where(PushSubscription.endpoint == payload.endpoint)
    ).scalar_one_or_none()

    if existing:
        existing.user_id = user_id
        existing.p256dh = payload.p256dh
        existing.auth = payload.auth
        db.add(existing)
        db.commit()
        db.refresh(existing)
        return existing

    sub = PushSubscription(user_id=user_id, **payload.model_dump())
    db.add(sub)
    db.commit()
    db.refresh(sub)
    return sub


def send_upcoming_notifications(db: Session, user_id: UUID, days: int = 3) -> int:
    """
    Sends push notifications for upcoming payables.
    Requires VAPID_PRIVATE_KEY, VAPID_PUBLIC_KEY, VAPID_CLAIMS_EMAIL env vars.
    Returns the number of notifications sent.
    """
    try:
        from pywebpush import webpush, WebPushException
    except ImportError:
        raise RuntimeError("pywebpush not installed. Add it to requirements.txt.")

    vapid_private = settings.vapid_private_key
    vapid_claims_email = settings.vapid_claims_email or "mailto:admin@example.com"

    if not vapid_private:
        raise RuntimeError("VAPID_PRIVATE_KEY environment variable not set.")

    today = date.today()
    until = today + timedelta(days=days)
    upcoming = db.execute(
        select(Payable).where(
            Payable.user_id == user_id,
            Payable.status == PayableStatus.PENDING,
            Payable.due_date >= today,
            Payable.due_date <= until,
        )
    ).scalars().all()

    if not upcoming:
        return 0

    subscriptions: List[PushSubscription] = db.execute(
        select(PushSubscription).where(PushSubscription.user_id == user_id)
    ).scalars().all()

    titles = [p.title for p in upcoming[:3]]
    body = f"Você tem {len(upcoming)} conta(s) vencendo em breve: {', '.join(titles)}"
    payload_data = json.dumps({"title": "LifeOS — Contas Vencendo", "body": body})

    sent = 0
    for sub in subscriptions:
        try:
            webpush(
                subscription_info={
                    "endpoint": sub.endpoint,
                    "keys": {"p256dh": sub.p256dh, "auth": sub.auth},
                },
                data=payload_data,
                vapid_private_key=vapid_private,
                vapid_claims={"sub": vapid_claims_email},
            )
            sent += 1
        except Exception:
            pass

    return sent
