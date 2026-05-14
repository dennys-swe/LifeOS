from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, ConfigDict


class PushSubscriptionCreate(BaseModel):
    endpoint: str
    p256dh: str
    auth: str


class PushSubscriptionResponse(PushSubscriptionCreate):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
