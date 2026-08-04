"""add status to credit_card_bills

Revision ID: a1b2c3d4e5f6
Revises: e0f1a2b3c4d5
Create Date: 2026-08-04 22:30:00.000000

Fatura fechada (Bills API da Pluggy) vs. ciclo ainda em aberto, reconstruído
das transações. Toda fatura já existente veio da Bills API, então o backfill
é CLOSED.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, None] = 'e0f1a2b3c4d5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bill_status = sa.Enum('OPEN', 'CLOSED', name='credit_card_bill_status')
    bill_status.create(op.get_bind(), checkfirst=True)
    op.add_column(
        'credit_card_bills',
        sa.Column('status', bill_status, nullable=False, server_default='CLOSED'),
    )


def downgrade() -> None:
    op.drop_column('credit_card_bills', 'status')
    sa.Enum(name='credit_card_bill_status').drop(op.get_bind(), checkfirst=True)
