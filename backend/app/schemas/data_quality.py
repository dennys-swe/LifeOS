from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel


class IssueTransaction(BaseModel):
    id: UUID
    date: date
    description: str
    amount: Decimal
    type: str
    is_transfer: bool
    category_name: Optional[str] = None


class DataQualityIssueResponse(BaseModel):
    id: UUID
    kind: str
    severity: str  # high | warn | info
    status: str  # open | resolved | dismissed
    detected_at: datetime
    detail: dict
    transactions: List[IssueTransaction]
    fix_available: bool
    needs_category: bool


class DataQualitySummaryResponse(BaseModel):
    open_total: int
    by_severity: Dict[str, int]
    by_kind: Dict[str, int]
    last_detected_at: Optional[datetime] = None


class RunAuditResponse(BaseModel):
    new: int
    unchanged: int
    reopened: int
    resolved: int


class TxChangeResponse(BaseModel):
    transaction_id: UUID
    description: str
    amount: Decimal
    date: date
    type: str
    field: str
    old: str
    new: str


class FixPreviewResponse(BaseModel):
    issue_id: UUID
    kind: str
    fix_available: bool
    needs_category: bool
    changes: List[TxChangeResponse]
    income_removed: Decimal
    expense_removed: Decimal
    already_fixed: bool


class ApplyFixRequest(BaseModel):
    category_id: Optional[UUID] = None
