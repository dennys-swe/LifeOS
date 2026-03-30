from __future__ import annotations

from enum import Enum
from uuid import uuid4

from sqlalchemy import Date, Enum as SAEnum, ForeignKey, Numeric, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base


class TransactionType(str, Enum):
    INCOME = "INCOME"
    EXPENSE = "EXPENSE"


class Transaction(Base):
    __tablename__ = "transactions"

    id: Mapped[Uuid] = mapped_column(Uuid, primary_key=True, default=uuid4)
    date: Mapped[Date] = mapped_column(Date, nullable=False)
    description: Mapped[str] = mapped_column(String(255), nullable=False)
    amount: Mapped[Numeric] = mapped_column(Numeric(12, 2), nullable=False)
    type: Mapped[TransactionType] = mapped_column(
        SAEnum(TransactionType, name="transaction_type"), nullable=False
    )
    source: Mapped[str | None] = mapped_column(String(100), nullable=True)
    category_id: Mapped[Uuid | None] = mapped_column(
        Uuid, ForeignKey("categories.id"), nullable=True
    )

    category = relationship("Category", back_populates="transactions")
