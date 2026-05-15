from __future__ import annotations

from datetime import date
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
    start_date: date = Field(default_factory=date.today)
    end_date: Optional[date] = None


class RecurringPayableUpdate(BaseModel):
    title: Optional[str] = Field(default=None, min_length=1, max_length=255)
    amount: Optional[Decimal] = Field(default=None, gt=0)
    day_of_month: Optional[int] = Field(default=None, ge=1, le=31)
    category_id: Optional[UUID] = None
    active: Optional[bool] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None


class RecurringPayableResponse(RecurringPayableCreate):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
