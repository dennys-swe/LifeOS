"""add kind to categories

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-08-05 00:20:00.000000

Separa categoria de receita de categoria de despesa. Todas as categorias que
existiam eram de gasto, então o backfill é EXPENSE.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c3d4e5f6a7b8'
down_revision: Union[str, None] = 'b2c3d4e5f6a7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    kind = sa.Enum('EXPENSE', 'INCOME', name='category_kind')
    kind.create(op.get_bind(), checkfirst=True)
    op.add_column(
        'categories',
        sa.Column('kind', kind, nullable=False, server_default='EXPENSE'),
    )


def downgrade() -> None:
    op.drop_column('categories', 'kind')
    sa.Enum(name='category_kind').drop(op.get_bind(), checkfirst=True)
