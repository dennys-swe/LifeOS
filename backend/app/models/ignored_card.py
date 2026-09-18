from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base


class IgnoredCard(Base):
    """Cartão que o usuário marcou como "não me importa mais" (ex: cancelado
    de verdade no banco, mas ainda aparece no sync porque a Pluggy demora a
    refletir ou a anuidade continua sendo cobrada em parcelas). Diferente de
    `retire_vanished_open_bills` (issue #25), que só age quando o cartão
    literalmente some da resposta da Pluggy — aqui o usuário decide na mão,
    mesmo com o cartão ainda ativo do lado da Pluggy.

    `pluggy_account_id` identifica o cartão (não `bank_account_id`, que é a
    conexão inteira e pode agrupar vários cartões — ex: MeuPluggy).
    """

    __tablename__ = "ignored_cards"
    __table_args__ = (
        UniqueConstraint(
            "user_id", "pluggy_account_id", name="uq_ignored_cards_user_id_pluggy_account_id"
        ),
    )

    id: Mapped[Uuid] = mapped_column(Uuid, primary_key=True, default=uuid4)
    user_id: Mapped[Uuid] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    bank_account_id: Mapped[Uuid] = mapped_column(
        Uuid, ForeignKey("bank_accounts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    pluggy_account_id: Mapped[str] = mapped_column(String(100), nullable=False)
    # Snapshot do rótulo no momento em que foi ignorado, só para exibição
    # (o cartão pode deixar de aparecer em qualquer CreditCardBill futuro).
    card_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
