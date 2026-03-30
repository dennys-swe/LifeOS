"""add categories and category_id

Revision ID: 9c1c3a4d7b21
Revises: 7ef993a38e0a
Create Date: 2026-03-29 20:05:00.000000
"""

from __future__ import annotations

from uuid import uuid4

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "9c1c3a4d7b21"
down_revision = "7ef993a38e0a"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "categories",
        sa.Column("id", sa.Uuid(), primary_key=True, nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False, unique=True),
        sa.Column("color_hex", sa.String(length=7), nullable=False),
    )

    op.add_column("transactions", sa.Column("category_id", sa.Uuid(), nullable=True))
    op.add_column("payables", sa.Column("category_id", sa.Uuid(), nullable=True))

    op.create_foreign_key(
        "fk_transactions_category",
        "transactions",
        "categories",
        ["category_id"],
        ["id"],
    )
    op.create_foreign_key(
        "fk_payables_category",
        "payables",
        "categories",
        ["category_id"],
        ["id"],
    )

    categories_table = sa.table(
        "categories",
        sa.column("id", sa.Uuid()),
        sa.column("name", sa.String()),
        sa.column("color_hex", sa.String()),
    )

    op.bulk_insert(
        categories_table,
        [
            {"id": uuid4(), "name": "Moradia", "color_hex": "#38BDF8"},
            {"id": uuid4(), "name": "Alimentação", "color_hex": "#22C55E"},
            {"id": uuid4(), "name": "Transporte", "color_hex": "#F97316"},
            {"id": uuid4(), "name": "Educação", "color_hex": "#6366F1"},
            {"id": uuid4(), "name": "Lazer", "color_hex": "#EC4899"},
            {"id": uuid4(), "name": "Mercado", "color_hex": "#84CC16"},
        ],
    )


def downgrade() -> None:
    op.drop_constraint("fk_transactions_category", "transactions", type_="foreignkey")
    op.drop_constraint("fk_payables_category", "payables", type_="foreignkey")
    op.drop_column("transactions", "category_id")
    op.drop_column("payables", "category_id")
    op.drop_table("categories")
