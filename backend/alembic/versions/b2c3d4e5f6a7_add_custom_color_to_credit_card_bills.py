"""add custom_color_hex to credit_card_bills

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-08-04 23:40:00.000000

Cor do cartão escolhida pelo usuário. Como o apelido, vale para o cartão
inteiro — é propagada a todas as faturas do mesmo `pluggy_account_id`.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b2c3d4e5f6a7'
down_revision: Union[str, None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'credit_card_bills',
        sa.Column('custom_color_hex', sa.String(length=7), nullable=True),
    )


def downgrade() -> None:
    op.drop_column('credit_card_bills', 'custom_color_hex')
