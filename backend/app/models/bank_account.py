from __future__ import annotations

from datetime import datetime
from enum import Enum
from uuid import uuid4

from sqlalchemy import DateTime, Enum as SAEnum, ForeignKey, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base


class BankAccountSyncStatus(str, Enum):
    IDLE = "IDLE"
    SYNCING = "SYNCING"
    ERROR = "ERROR"


class BankAccount(Base):
    __tablename__ = "bank_accounts"

    id: Mapped[Uuid] = mapped_column(Uuid, primary_key=True, default=uuid4)
    user_id: Mapped[Uuid] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    bank_name: Mapped[str] = mapped_column(String(100), nullable=False)
    account_type: Mapped[str] = mapped_column(String(20), nullable=False, default="checking")
    external_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    last_sync_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    sync_status: Mapped[BankAccountSyncStatus] = mapped_column(
        SAEnum(BankAccountSyncStatus, name="bank_account_sync_status"),
        nullable=False,
        default=BankAccountSyncStatus.IDLE,
    )
    last_sync_error: Mapped[str | None] = mapped_column(Text, nullable=True)
