"""add category rules

Revision ID: 0457df89e3bd
Revises: 9404d293bd64
Create Date: 2026-05-13

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0457df89e3bd"
down_revision: Union[str, None] = "9404d293bd64"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "category_rules",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("keyword", sa.String(100), nullable=False),
        sa.Column("category_id", sa.Uuid(), nullable=False),
        sa.Column("priority", sa.Integer(), nullable=False, server_default="0"),
        sa.ForeignKeyConstraint(["category_id"], ["categories.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_category_rules_keyword", "category_rules", ["keyword"])


def downgrade() -> None:
    op.drop_index("ix_category_rules_keyword", "category_rules")
    op.drop_table("category_rules")
