from __future__ import annotations

from enum import Enum
from uuid import uuid4

from sqlalchemy import Boolean, Date, Enum as SAEnum, ForeignKey, Index, Numeric, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base


class TransactionType(str, Enum):
    INCOME = "INCOME"
    EXPENSE = "EXPENSE"


class Transaction(Base):
    __tablename__ = "transactions"
    __table_args__ = (
        Index("ix_transactions_user_id_source", "user_id", "source"),
    )

    id: Mapped[Uuid] = mapped_column(Uuid, primary_key=True, default=uuid4)
    user_id: Mapped[Uuid] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    date: Mapped[Date] = mapped_column(Date, nullable=False)
    description: Mapped[str] = mapped_column(String(255), nullable=False)
    amount: Mapped[Numeric] = mapped_column(Numeric(12, 2), nullable=False)
    type: Mapped[TransactionType] = mapped_column(
        SAEnum(TransactionType, name="transaction_type"), nullable=False
    )
    source: Mapped[str | None] = mapped_column(String(100), nullable=True)
    # Dinheiro que só muda de lugar (quitação de fatura, transferência entre as
    # próprias contas, aporte em investimento). Continua registrado, mas é
    # excluído dos totais de gasto — senão a mesma grana conta duas vezes.
    is_transfer: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    # Categoria crua da Pluggy, preservada para permitir re-mapear sem
    # re-consultar a API.
    external_category: Mapped[str | None] = mapped_column(String(80), nullable=True)
    category_id: Mapped[Uuid | None] = mapped_column(
        Uuid, ForeignKey("categories.id"), nullable=True
    )

    category = relationship("Category", back_populates="transactions")
