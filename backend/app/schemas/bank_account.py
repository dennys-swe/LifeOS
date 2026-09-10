from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.bank_account import BankAccountSyncStatus


class BankAccountCreate(BaseModel):
    """`name`/`bank_name` são opcionais: quando vêm vazios e há `external_id`, o
    backend deriva o rótulo das accounts da Pluggy (com o conector MeuPluggy o
    frontend só conhece `connector.name == "MeuPluggy"`, igual para todo banco).
    """

    name: Optional[str] = Field(default=None, min_length=1, max_length=100)
    bank_name: Optional[str] = Field(default=None, min_length=1, max_length=100)
    account_type: str = Field(default="checking", pattern="^(checking|savings|credit)$")
    external_id: Optional[str] = None


class BankAccountUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=100)
    bank_name: Optional[str] = Field(default=None, min_length=1, max_length=100)


class BankAccountResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    bank_name: str
    account_type: str
    external_id: Optional[str] = None
    last_sync_at: Optional[datetime] = None
    sync_started_at: Optional[datetime] = None
    sync_status: BankAccountSyncStatus = BankAccountSyncStatus.IDLE
    last_sync_error: Optional[str] = None
