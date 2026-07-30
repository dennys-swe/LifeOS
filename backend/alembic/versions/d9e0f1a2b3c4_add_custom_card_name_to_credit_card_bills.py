"""add custom_card_name to credit_card_bills

Permite definir um apelido customizado/alias para faturas de cartão de crédito.

Revision ID: d9e0f1a2b3c4
Revises: b8c9d0e1f2a3
Create Date: 2026-07-30 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "d9e0f1a2b3c4"
down_revision: Union[str, Sequence[str], None] = "b8c9d0e1f2a3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "credit_card_bills",
        sa.Column("custom_card_name", sa.String(length=100), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("credit_card_bills", "custom_card_name")
