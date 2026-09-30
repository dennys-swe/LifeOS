from __future__ import annotations

from enum import Enum
from uuid import uuid4

from sqlalchemy import (
    Boolean,
    Date,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base


class TransactionType(str, Enum):
    INCOME = "INCOME"
    EXPENSE = "EXPENSE"


class ClassificationSource:
    """De onde veio a categoria/`is_transfer` da transação (issue #167).

    Precedência de decisão, da mais forte para a mais fraca: `MANUAL_OVERRIDE`
    (correção do usuário, travada contra reprocessamento) > `USER_RULE` >
    `PLUGGY` (categoria/campos estruturados) > `SYSTEM_RULE` (regex do sistema).
    `None` = transação anterior a esse campo, origem desconhecida.
    """

    MANUAL_OVERRIDE = "manual_override"
    USER_RULE = "user_rule"
    PLUGGY = "pluggy"
    SYSTEM_RULE = "system_rule"


class Transaction(Base):
    __tablename__ = "transactions"
    __table_args__ = (
        # Era só um índice (o dedup do sync fazia um SELECT por transação
        # pra checar, então a unicidade nunca dependia do banco). Virou
        # constraint de verdade na issue #8: o sync agora deduplica em
        # memória, e a constraint é a rede de segurança contra uma corrida
        # (dois syncs da mesma conta em paralelo) ou um bug futuro que
        # reintroduza um INSERT duplicado. NULL não colide consigo mesmo em
        # Postgres, então transações manuais (source=None) não são afetadas.
        UniqueConstraint("user_id", "source", name="uq_transactions_user_id_source"),
        # Suporta o dedup por similaridade contra transações já persistidas
        # (bank_sync_service._dedup_against_existing, issue de dedup entre
        # syncs) — sem isso, cada sync faz um range scan em `date` sem índice.
        Index("ix_transactions_user_id_date", "user_id", "date"),
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
    # Campos estruturados da Pluggy que o sync antes descartava (#167). O Inter,
    # por exemplo, manda 39 parcelas só aqui, sem "X/Y" na descrição.
    installment_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    installment_total: Mapped[int | None] = mapped_column(Integer, nullable=True)
    pluggy_category_id: Mapped[str | None] = mapped_column(String(20), nullable=True)
    operation_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    bill_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    classification_source: Mapped[str | None] = mapped_column(String(20), nullable=True)
    # De qual cartão/conta veio (#184). `card_label` = "<nome> ••<final>" quando a
    # Pluggy manda `cardNumber` (Itaú Múltiplo junta vários cartões numa mesma
    # `accountId`, então só o id da conta não separa); só o nome quando não manda
    # (Inter). Transação manual e anterior a esse campo ficam NULL.
    card_label: Mapped[str | None] = mapped_column(String(120), nullable=True)
    pluggy_account_id: Mapped[str | None] = mapped_column(String(100), nullable=True)

    category = relationship("Category", back_populates="transactions")
