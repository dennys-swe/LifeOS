"""transactions: card_label + pluggy_account_id

Revision ID: b2c3d4e5f6a8
Revises: a1b2c3d4e5f7
Create Date: 2026-09-30 15:00:00.000000

Selo de cartão/conta em cada transação (#184). Nullable, sem backfill.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b2c3d4e5f6a8"
down_revision: Union[str, Sequence[str], None] = "a1b2c3d4e5f7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("transactions", sa.Column("card_label", sa.String(120), nullable=True))
    op.add_column("transactions", sa.Column("pluggy_account_id", sa.String(100), nullable=True))


def downgrade() -> None:
    op.drop_column("transactions", "pluggy_account_id")
    op.drop_column("transactions", "card_label")
