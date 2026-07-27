from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.bank_account import BankAccountSyncStatus


class BankAccountCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    bank_name: str = Field(min_length=1, max_length=100)
    account_type: str = Field(default="checking", pattern="^(checking|savings|credit)$")
    external_id: Optional[str] = None


class BankAccountResponse(BankAccountCreate):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    last_sync_at: Optional[datetime] = None
    sync_status: BankAccountSyncStatus = BankAccountSyncStatus.IDLE
    last_sync_error: Optional[str] = None
