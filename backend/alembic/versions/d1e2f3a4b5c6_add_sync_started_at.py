"""add bank_accounts.sync_started_at

Revision ID: d1e2f3a4b5c6
Revises: c3d4e5f6a7b8
Create Date: 2026-09-10 06:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "d1e2f3a4b5c6"
down_revision: Union[str, Sequence[str], None] = "c3d4e5f6a7b8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("bank_accounts", sa.Column("sync_started_at", sa.DateTime(), nullable=True))


def downgrade() -> None:
    op.drop_column("bank_accounts", "sync_started_at")
