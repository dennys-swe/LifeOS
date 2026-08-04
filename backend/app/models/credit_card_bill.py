from __future__ import annotations

from datetime import date, datetime
from enum import Enum
from uuid import uuid4

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Enum as SAEnum,
    ForeignKey,
    Numeric,
    String,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base


class CreditCardBillStatus(str, Enum):
    """Fatura fechada pelo banco vs. ciclo ainda em aberto.

    `CLOSED` vem da Bills API da Pluggy — é o valor oficial e definitivo.
    `OPEN` é reconstruída a partir das transações do ciclo corrente, porque a
    Bills API só publica a fatura depois do fechamento (dias ou semanas de
    atraso, variando por banco). Só fatura `CLOSED` vira `Payable`: o valor de
    uma fatura aberta muda a cada compra, não é obrigação firme.
    """

    OPEN = "OPEN"
    CLOSED = "CLOSED"


class CreditCardBill(Base):
    __tablename__ = "credit_card_bills"
    __table_args__ = (
        UniqueConstraint("user_id", "external_id", name="uq_credit_card_bills_user_id_external_id"),
    )

    id: Mapped[Uuid] = mapped_column(Uuid, primary_key=True, default=uuid4)
    user_id: Mapped[Uuid] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    bank_account_id: Mapped[Uuid] = mapped_column(
        Uuid, ForeignKey("bank_accounts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    pluggy_account_id: Mapped[str] = mapped_column(String(100), nullable=False)
    external_id: Mapped[str] = mapped_column(String(100), nullable=False)
    card_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    custom_card_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    due_date: Mapped[date] = mapped_column(Date, nullable=False)
    total_amount: Mapped[Numeric] = mapped_column(Numeric(12, 2), nullable=False)
    status: Mapped[CreditCardBillStatus] = mapped_column(
        SAEnum(CreditCardBillStatus, name="credit_card_bill_status"),
        nullable=False,
        default=CreditCardBillStatus.CLOSED,
        server_default=CreditCardBillStatus.CLOSED.value,
    )
    minimum_payment_amount: Mapped[Numeric | None] = mapped_column(Numeric(12, 2), nullable=True)
    allows_installments: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    payable_id: Mapped[Uuid | None] = mapped_column(
        Uuid, ForeignKey("payables.id", ondelete="SET NULL"), nullable=True
    )
    synced_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)

    bank_account = relationship("BankAccount")
    payable = relationship("Payable")
