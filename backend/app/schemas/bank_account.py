from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, computed_field

from app.models.bank_account import BankAccountSyncStatus
from app.services.connection_freshness import ConnectionFreshness, assess_connection_freshness


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

    # Idade real do dado (#214): quando a Pluggy leu o banco, não quando o LifeOS leu a Pluggy.
    item_status: Optional[str] = None
    item_last_updated_at: Optional[datetime] = None
    item_next_auto_sync_at: Optional[datetime] = None
    consent_expires_at: Optional[datetime] = None
    item_checked_at: Optional[datetime] = None
    item_user_action: Optional[str] = None

    @computed_field  # type: ignore[prop-decorator]
    @property
    def freshness(self) -> ConnectionFreshness:
        return assess_connection_freshness(
            item_checked_at=self.item_checked_at,
            item_status=self.item_status,
            item_user_action=self.item_user_action,
            item_last_updated_at=self.item_last_updated_at,
            item_next_auto_sync_at=self.item_next_auto_sync_at,
            consent_expires_at=self.consent_expires_at,
        )
