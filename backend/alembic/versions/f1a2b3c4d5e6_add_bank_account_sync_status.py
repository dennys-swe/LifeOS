"""add bank account sync status

Revision ID: f1a2b3c4d5e6
Revises: ae3884e5cebe
Create Date: 2026-07-27 20:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f1a2b3c4d5e6'
down_revision: Union[str, Sequence[str], None] = 'ae3884e5cebe'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


bank_account_sync_status = sa.Enum(
    "IDLE", "SYNCING", "ERROR", name="bank_account_sync_status"
)


def upgrade() -> None:
    bank_account_sync_status.create(op.get_bind(), checkfirst=True)
    op.add_column(
        "bank_accounts",
        sa.Column(
            "sync_status",
            bank_account_sync_status,
            nullable=False,
            server_default="IDLE",
        ),
    )
    op.add_column("bank_accounts", sa.Column("last_sync_error", sa.Text(), nullable=True))
    op.alter_column("bank_accounts", "sync_status", server_default=None)


def downgrade() -> None:
    op.drop_column("bank_accounts", "last_sync_error")
    op.drop_column("bank_accounts", "sync_status")
    bank_account_sync_status.drop(op.get_bind(), checkfirst=True)
