from __future__ import annotations

from decimal import Decimal
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class RecurringPayableCreate(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    amount: Decimal = Field(gt=0)
    day_of_month: int = Field(ge=1, le=31)
    category_id: Optional[UUID] = None
    active: bool = True


class RecurringPayableUpdate(BaseModel):
    title: Optional[str] = Field(default=None, min_length=1, max_length=255)
    amount: Optional[Decimal] = Field(default=None, gt=0)
    day_of_month: Optional[int] = Field(default=None, ge=1, le=31)
    category_id: Optional[UUID] = None
    active: Optional[bool] = None


class RecurringPayableResponse(RecurringPayableCreate):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
