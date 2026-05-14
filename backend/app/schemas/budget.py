from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class BudgetCreate(BaseModel):
    category_id: UUID
    month: int = Field(ge=1, le=12)
    year: int = Field(ge=2000, le=2100)
    limit_amount: Decimal = Field(gt=0)


class BudgetResponse(BudgetCreate):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
