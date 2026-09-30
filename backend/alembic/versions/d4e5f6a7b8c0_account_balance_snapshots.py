"""account_balance_snapshots

Revision ID: d4e5f6a7b8c0
Revises: c3d4e5f6a7b9
Create Date: 2026-10-01 10:00:00.000000

Fotos de saldo (conta corrente) e limite (cartão) por sync (#197).
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d4e5f6a7b8c0"
down_revision: Union[str, Sequence[str], None] = "c3d4e5f6a7b9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "account_balance_snapshots",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("bank_account_id", sa.Uuid(), nullable=False),
        sa.Column("pluggy_account_id", sa.String(length=100), nullable=False),
        sa.Column("account_type", sa.String(length=10), nullable=False),
        sa.Column("balance", sa.Numeric(14, 2), nullable=True),
        sa.Column("credit_limit", sa.Numeric(14, 2), nullable=True),
        sa.Column("available_credit_limit", sa.Numeric(14, 2), nullable=True),
        sa.Column("currency", sa.String(length=3), nullable=True),
        sa.Column("captured_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["bank_account_id"], ["bank_accounts.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_account_balance_snapshots_user_id", "account_balance_snapshots", ["user_id"]
    )
    op.create_index(
        "ix_account_balance_snapshots_bank_account_captured",
        "account_balance_snapshots",
        ["bank_account_id", "captured_at"],
    )
    op.create_index(
        "ix_account_balance_snapshots_user_pluggy_captured",
        "account_balance_snapshots",
        ["user_id", "pluggy_account_id", "captured_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_account_balance_snapshots_user_pluggy_captured", table_name="account_balance_snapshots"
    )
    op.drop_index(
        "ix_account_balance_snapshots_bank_account_captured", table_name="account_balance_snapshots"
    )
    op.drop_index("ix_account_balance_snapshots_user_id", table_name="account_balance_snapshots")
    op.drop_table("account_balance_snapshots")
