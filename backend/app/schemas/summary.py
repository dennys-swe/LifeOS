from __future__ import annotations

from decimal import Decimal
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel


class CategorySummary(BaseModel):
    category_id: Optional[UUID]
    category_name: str
    color_hex: str
    total_payables: Decimal
    total_transactions: Decimal
    budget_limit: Optional[Decimal] = None
    budget_used_pct: Optional[float] = None


class SummaryResponse(BaseModel):
    total_income: Decimal
    total_expenses: Decimal
    total_pending: Decimal
    total_paid: Decimal
    balance: Decimal
    by_category: List[CategorySummary]


class MonthSummary(BaseModel):
    month: int
    year: int
    total_income: Decimal
    total_expenses: Decimal
    total_pending: Decimal
    total_paid: Decimal
    balance: Decimal


class HistoryResponse(BaseModel):
    months: List[MonthSummary]
