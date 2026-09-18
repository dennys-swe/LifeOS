"""add ignored_cards

Revision ID: c4d5e6f7a8b9
Revises: b3c4d5e6f7a8
Create Date: 2026-09-18 00:00:00.000000

Cartão que o usuário decide ignorar manualmente (ex: cancelado no banco, mas
a Pluggy continua devolvendo cobrança de anuidade parcelada). Diferente da
retirada automática de cartão sumido (issue #25): aqui o cartão pode
continuar ativo do lado da Pluggy, e é o usuário quem decide parar de
rastreá-lo.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c4d5e6f7a8b9"
down_revision: Union[str, Sequence[str], None] = "b3c4d5e6f7a8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "ignored_cards",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("bank_account_id", sa.Uuid(), nullable=False),
        sa.Column("pluggy_account_id", sa.String(length=100), nullable=False),
        sa.Column("card_name", sa.String(length=100), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["bank_account_id"], ["bank_accounts.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "user_id", "pluggy_account_id", name="uq_ignored_cards_user_id_pluggy_account_id"
        ),
    )
    op.create_index(
        op.f("ix_ignored_cards_user_id"), "ignored_cards", ["user_id"], unique=False
    )
    op.create_index(
        op.f("ix_ignored_cards_bank_account_id"),
        "ignored_cards",
        ["bank_account_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_ignored_cards_bank_account_id"), table_name="ignored_cards")
    op.drop_index(op.f("ix_ignored_cards_user_id"), table_name="ignored_cards")
    op.drop_table("ignored_cards")
