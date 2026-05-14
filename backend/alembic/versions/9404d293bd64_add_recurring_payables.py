"""add recurring payables

Revision ID: 9404d293bd64
Revises: 9c1c3a4d7b21
Create Date: 2026-05-13

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "9404d293bd64"
down_revision: Union[str, None] = "9c1c3a4d7b21"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "recurring_payables",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("day_of_month", sa.Integer(), nullable=False),
        sa.Column("category_id", sa.Uuid(), nullable=True),
        sa.Column("active", sa.Boolean(), nullable=False, server_default="true"),
        sa.ForeignKeyConstraint(["category_id"], ["categories.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.add_column("payables", sa.Column("recurring_payable_id", sa.Uuid(), nullable=True))
    op.create_foreign_key(
        "fk_payables_recurring",
        "payables",
        "recurring_payables",
        ["recurring_payable_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("fk_payables_recurring", "payables", type_="foreignkey")
    op.drop_column("payables", "recurring_payable_id")
    op.drop_table("recurring_payables")
