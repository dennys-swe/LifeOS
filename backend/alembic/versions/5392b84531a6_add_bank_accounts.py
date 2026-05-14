"""add bank accounts

Revision ID: 5392b84531a6
Revises: 86c789c5500b
Create Date: 2026-05-13

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "5392b84531a6"
down_revision: Union[str, None] = "86c789c5500b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "bank_accounts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("bank_name", sa.String(100), nullable=False),
        sa.Column("account_type", sa.String(20), nullable=False, server_default="checking"),
        sa.Column("external_id", sa.String(100), nullable=True),
        sa.Column("last_sync_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("bank_accounts")
