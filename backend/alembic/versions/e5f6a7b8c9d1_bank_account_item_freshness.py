"""bank_accounts: estado do item na Pluggy

Revision ID: e5f6a7b8c9d1
Revises: d4e5f6a7b8c0
Create Date: 2026-10-01 12:00:00.000000

Idade real do dado por conexão (#214).
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e5f6a7b8c9d1"
down_revision: Union[str, Sequence[str], None] = "d4e5f6a7b8c0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_COLUMNS = (
    ("item_status", sa.String(length=40)),
    ("item_execution_status", sa.String(length=40)),
    ("item_user_action", sa.String(length=80)),
    ("item_last_updated_at", sa.DateTime()),
    ("item_next_auto_sync_at", sa.DateTime()),
    ("consent_expires_at", sa.DateTime()),
    ("item_checked_at", sa.DateTime()),
)


def upgrade() -> None:
    for name, type_ in _COLUMNS:
        op.add_column("bank_accounts", sa.Column(name, type_, nullable=True))


def downgrade() -> None:
    for name, _ in reversed(_COLUMNS):
        op.drop_column("bank_accounts", name)
