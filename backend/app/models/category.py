from __future__ import annotations

from enum import Enum
from uuid import uuid4

from sqlalchemy import Enum as SAEnum, ForeignKey, String, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base


class CategoryKind(str, Enum):
    """Categoria de gasto vs. de receita.

    Sem essa separação não havia destino para dinheiro recebido, e o mapa da
    Pluggy mandava PIX recebido para "Transferências" — categoria criada para
    PIX **enviado**. Nos dados reais do dono eram 202 entradas (R$ 58.542,65)
    morando numa categoria de despesa.
    """

    EXPENSE = "EXPENSE"
    INCOME = "INCOME"


class Category(Base):
    __tablename__ = "categories"
    __table_args__ = (
        UniqueConstraint("user_id", "name", name="uq_categories_user_id_name"),
    )

    id: Mapped[Uuid] = mapped_column(Uuid, primary_key=True, default=uuid4)
    user_id: Mapped[Uuid] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    color_hex: Mapped[str] = mapped_column(String(7), nullable=False)
    kind: Mapped[CategoryKind] = mapped_column(
        SAEnum(CategoryKind, name="category_kind"),
        nullable=False,
        default=CategoryKind.EXPENSE,
        server_default=CategoryKind.EXPENSE.value,
    )

    transactions = relationship("Transaction", back_populates="category")
    payables = relationship("Payable", back_populates="category")