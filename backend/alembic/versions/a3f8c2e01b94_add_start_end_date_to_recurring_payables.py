"""add start_date and end_date to recurring_payables

Revision ID: a3f8c2e01b94
Revises: e6c8bbf86fe1
Create Date: 2026-05-15

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "a3f8c2e01b94"
down_revision: Union[str, None] = "c4fb13f3a423"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "recurring_payables",
        sa.Column("start_date", sa.Date(), nullable=False, server_default=sa.text("CURRENT_DATE")),
    )
    op.add_column(
        "recurring_payables",
        sa.Column("end_date", sa.Date(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("recurring_payables", "end_date")
    op.drop_column("recurring_payables", "start_date")
