"""transactions: index (user_id, date)

Revision ID: b3c4d5e6f7a8
Revises: f9a0b1c2d3e4
Create Date: 2026-09-17 16:00:00.000000

`bank_sync_service._dedup_against_existing` (dedup por similaridade contra
transações já persistidas, achado na auditoria de extrato) faz um range scan
em `date` por `user_id` a cada sync — sem índice composto, cresce sem limite
junto com o histórico do usuário.
"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b3c4d5e6f7a8"
down_revision: Union[str, Sequence[str], None] = "f9a0b1c2d3e4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index(
        "ix_transactions_user_id_date", "transactions", ["user_id", "date"]
    )


def downgrade() -> None:
    op.drop_index("ix_transactions_user_id_date", table_name="transactions")
