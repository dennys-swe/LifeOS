"""add reconciliation transaction_id to payables

Revision ID: e6c8bbf86fe1
Revises: 0457df89e3bd
Create Date: 2026-05-13

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "e6c8bbf86fe1"
down_revision: Union[str, None] = "0457df89e3bd"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("payables", sa.Column("transaction_id", sa.Uuid(), nullable=True))
    op.create_foreign_key(
        "fk_payables_transaction",
        "payables",
        "transactions",
        ["transaction_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("fk_payables_transaction", "payables", type_="foreignkey")
    op.drop_column("payables", "transaction_id")
