from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from sqlalchemy import JSON, DateTime, ForeignKey, Index, String, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base


class DataQualityIssue(Base):
    """Suspeita de classificação errada achada pela auditoria (#199).

    A auditoria só **sinaliza**: nada aqui altera a transação. `fingerprint` (kind + ids
    ordenados) torna a gravação idempotente: rodar de novo não duplica. `status`: `open`,
    `resolved` (a auditoria deixou de achar o problema) ou `dismissed` (o usuário disse que
    está certo; nunca é reaberto pela auditoria).
    """

    __tablename__ = "data_quality_issues"
    __table_args__ = (
        UniqueConstraint("user_id", "fingerprint", name="uq_data_quality_issues_user_fingerprint"),
        Index("ix_data_quality_issues_user_status", "user_id", "status"),
    )

    id: Mapped[Uuid] = mapped_column(Uuid, primary_key=True, default=uuid4)
    user_id: Mapped[Uuid] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    kind: Mapped[str] = mapped_column(String(40), nullable=False)
    severity: Mapped[str] = mapped_column(String(10), nullable=False)
    status: Mapped[str] = mapped_column(String(10), nullable=False, default="open")
    fingerprint: Mapped[str] = mapped_column(String(40), nullable=False)
    transaction_ids: Mapped[list] = mapped_column(JSON, nullable=False)
    detail: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    detected_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
