from __future__ import annotations

from uuid import uuid4

from sqlalchemy import Boolean, ForeignKey, Integer, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base


class CategoryRule(Base):
    __tablename__ = "category_rules"

    id: Mapped[Uuid] = mapped_column(Uuid, primary_key=True, default=uuid4)
    user_id: Mapped[Uuid] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    keyword: Mapped[str] = mapped_column(String(100), nullable=False)
    category_id: Mapped[Uuid] = mapped_column(Uuid, ForeignKey("categories.id"), nullable=False)
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # Dinheiro que só muda de mão sob esse padrão (ex: divisão de contas com
    # alguém que não é o próprio usuário na Pluggy) não é receita nem gasto de
    # verdade — a regra pode marcar isso além de dar categoria, já que
    # `is_transfer` normalmente só vem de `pluggy_category_map` (categoria da
    # Pluggy ou descrição de pagamento de fatura), que não sabe reconhecer uma
    # pessoa específica.
    is_transfer: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )

    category = relationship("Category")
