"""transactions: campos estruturados da Pluggy + classification_source

Revision ID: a1b2c3d4e5f7
Revises: 925d1d5f0368
Create Date: 2026-09-30 12:00:00.000000

O sync descartava `creditCardMetadata` (parcelas, billId), `categoryId` e
`operationType`. Todas as colunas são nullable: transações antigas ficam sem o
dado (sem backfill) e `classification_source` NULL significa origem desconhecida.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4e5f7"
down_revision: Union[str, Sequence[str], None] = "925d1d5f0368"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("transactions", sa.Column("installment_number", sa.Integer(), nullable=True))
    op.add_column("transactions", sa.Column("installment_total", sa.Integer(), nullable=True))
    op.add_column("transactions", sa.Column("pluggy_category_id", sa.String(20), nullable=True))
    op.add_column("transactions", sa.Column("operation_type", sa.String(50), nullable=True))
    op.add_column("transactions", sa.Column("bill_id", sa.String(100), nullable=True))
    op.add_column("transactions", sa.Column("classification_source", sa.String(20), nullable=True))


def downgrade() -> None:
    for col in (
        "classification_source",
        "bill_id",
        "operation_type",
        "pluggy_category_id",
        "installment_total",
        "installment_number",
    ):
        op.drop_column("transactions", col)
