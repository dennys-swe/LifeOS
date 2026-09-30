from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class CardLimitResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    pluggy_account_id: str
    bank_account_id: UUID
    label: str
    status: str  # ok | no_limit | inconsistent
    credit_limit: Optional[Decimal] = None
    available: Optional[Decimal] = None
    used: Optional[Decimal] = None
    used_pct: Optional[float] = None
    captured_at: datetime
    freshness_state: str  # fresh | stale | attention | unknown


class CardLimitsResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    cards: List[CardLimitResponse]
    total_limit: Decimal
    total_used: Decimal
    total_available: Decimal
    used_pct: Optional[float] = None
    cards_counted: int
    cards_ignored: int
    cards_without_limit: int
    cards_inconsistent: int
    freshness_state: str
