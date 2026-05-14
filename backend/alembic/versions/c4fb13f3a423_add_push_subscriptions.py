"""add push subscriptions

Revision ID: c4fb13f3a423
Revises: 5392b84531a6
Create Date: 2026-05-13

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "c4fb13f3a423"
down_revision: Union[str, None] = "5392b84531a6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "push_subscriptions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("endpoint", sa.Text(), nullable=False),
        sa.Column("p256dh", sa.String(200), nullable=False),
        sa.Column("auth", sa.String(50), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("endpoint", name="uq_push_subscriptions_endpoint"),
    )


def downgrade() -> None:
    op.drop_table("push_subscriptions")
