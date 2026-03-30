from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.payable import PayableStatus


class PayableBase(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    amount: Decimal = Field(gt=0)
    due_date: date
    status: PayableStatus = PayableStatus.PENDING
    payment_date: Optional[date] = None
    category_id: Optional[UUID] = None


class PayableCreate(PayableBase):
    pass


class PayableUpdate(BaseModel):
    title: Optional[str] = Field(default=None, min_length=1, max_length=255)
    amount: Optional[Decimal] = Field(default=None, gt=0)
    due_date: Optional[date] = None
    status: Optional[PayableStatus] = None
    payment_date: Optional[date] = None
    category_id: Optional[UUID] = None


class PayableResponse(PayableBase):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
