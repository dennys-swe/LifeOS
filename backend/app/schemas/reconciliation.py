from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel


class ReconciliationSuggestionResponse(BaseModel):
    transaction_id: UUID
    payable_id: UUID
    confidence_score: float
    payable_title: str
    payable_amount: Decimal
    transaction_description: str
    transaction_amount: Decimal
