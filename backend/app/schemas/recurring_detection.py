from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel, Field


class RecurringSuggestion(BaseModel):
    title: str
    amount: Decimal
    day_of_month: int = Field(ge=1, le=31)
    occurrences: int
    distinct_months: int
