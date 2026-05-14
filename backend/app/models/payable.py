from __future__ import annotations

from enum import Enum
from uuid import uuid4

from sqlalchemy import Date, Enum as SAEnum, ForeignKey, Numeric, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base


class PayableStatus(str, Enum):
    PENDING = "PENDING"
    PAID = "PAID"
    OVERDUE = "OVERDUE"


class Payable(Base):
    __tablename__ = "payables"

    id: Mapped[Uuid] = mapped_column(Uuid, primary_key=True, default=uuid4)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    amount: Mapped[Numeric] = mapped_column(Numeric(12, 2), nullable=False)
    due_date: Mapped[Date] = mapped_column(Date, nullable=False)
    status: Mapped[PayableStatus] = mapped_column(
        SAEnum(PayableStatus, name="payable_status"),
        nullable=False,
        default=PayableStatus.PENDING,
    )
    payment_date: Mapped[Date | None] = mapped_column(Date, nullable=True)
    category_id: Mapped[Uuid | None] = mapped_column(
        Uuid, ForeignKey("categories.id"), nullable=True
    )
    recurring_payable_id: Mapped[Uuid | None] = mapped_column(
        Uuid, ForeignKey("recurring_payables.id", ondelete="SET NULL"), nullable=True
    )
    transaction_id: Mapped[Uuid | None] = mapped_column(
        Uuid, ForeignKey("transactions.id", ondelete="SET NULL"), nullable=True
    )

    category = relationship("Category", back_populates="payables")
    recurring_payable = relationship("RecurringPayable", back_populates="payables")
    transaction = relationship("Transaction")
