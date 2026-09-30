from __future__ import annotations

from datetime import datetime
from enum import Enum
from uuid import uuid4

from sqlalchemy import DateTime, ForeignKey, String, Text, Uuid
from sqlalchemy import Enum as SAEnum
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
    # Início da sincronização em andamento. Um lock SYNCING mais velho que
    # STALE_SYNC_LOCK (ver bank_sync_service) é considerado morto — o job em
    # background morreu (Render free recicla o worker) sem voltar para IDLE.
    sync_started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    sync_status: Mapped[BankAccountSyncStatus] = mapped_column(
        SAEnum(BankAccountSyncStatus, name="bank_account_sync_status"),
        nullable=False,
        default=BankAccountSyncStatus.IDLE,
    )
    last_sync_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Estado do *item* na Pluggy (#214), lido a cada sync. `last_sync_at` diz quando o
    # LifeOS leu a Pluggy; estes dizem quando a Pluggy leu o **banco**. Um item pode ficar
    # dias sem atualizar (ex: `next_auto_sync_at` nulo) com `last_sync_at` de hoje.
    item_status: Mapped[str | None] = mapped_column(String(40), nullable=True)
    item_execution_status: Mapped[str | None] = mapped_column(String(40), nullable=True)
    item_user_action: Mapped[str | None] = mapped_column(String(80), nullable=True)
    item_last_updated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    item_next_auto_sync_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    consent_expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    item_checked_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
