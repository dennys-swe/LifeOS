from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.models.credit_card_bill import CreditCardBillStatus


class CreditCardBillResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    bank_account_id: UUID
    card_name: Optional[str] = None
    custom_card_name: Optional[str] = None
    due_date: date
    total_amount: Decimal
    minimum_payment_amount: Optional[Decimal]
    allows_installments: Optional[bool]
    payable_id: Optional[UUID]
    status: CreditCardBillStatus


class CreditCardBillUpdate(BaseModel):
    custom_card_name: Optional[str] = None

