from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import uuid4

from sqlalchemy import DateTime, ForeignKey, Index, Numeric, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base


class AccountBalanceSnapshot(Base):
    """Foto do saldo (conta corrente) ou do limite (cartão) de uma conta da Pluggy.

    Semântica confirmada contra a API real (#196, `tests/fixtures/pluggy/README.md`):

    - `balance` de `BANK` é o saldo da conta (igual a `bankData.closingBalance`);
    - `balance` de `CREDIT` é o limite **consumido**, igual a `credit_limit - available_credit_limit`,
      e **não** o valor da fatura;
    - `credit_limit` / `available_credit_limit` são da conta Pluggy e compartilhados entre
      os cartões dela; só existem em `CREDIT`.

    Base da conciliação de saldo (#198) e do limite consolidado (#204). `pluggy_account_id`
    identifica a conta (não `bank_account_id`, que é a conexão inteira e agrupa várias).
    """

    __tablename__ = "account_balance_snapshots"
    __table_args__ = (
        Index(
            "ix_account_balance_snapshots_bank_account_captured", "bank_account_id", "captured_at"
        ),
        Index(
            "ix_account_balance_snapshots_user_pluggy_captured",
            "user_id",
            "pluggy_account_id",
            "captured_at",
        ),
    )

    id: Mapped[Uuid] = mapped_column(Uuid, primary_key=True, default=uuid4)
    user_id: Mapped[Uuid] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    bank_account_id: Mapped[Uuid] = mapped_column(
        Uuid, ForeignKey("bank_accounts.id", ondelete="CASCADE"), nullable=False
    )
    pluggy_account_id: Mapped[str] = mapped_column(String(100), nullable=False)
    account_type: Mapped[str] = mapped_column(String(10), nullable=False)  # BANK | CREDIT
    balance: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    credit_limit: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    available_credit_limit: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    currency: Mapped[str | None] = mapped_column(String(3), nullable=True)
    captured_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
