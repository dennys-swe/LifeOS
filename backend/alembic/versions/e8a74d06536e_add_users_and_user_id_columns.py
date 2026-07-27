"""add users and user_id columns

Revision ID: e8a74d06536e
Revises: a3f8c2e01b94
Create Date: 2026-07-27 13:47:17.900148

Parte 1/2 da migração multi-tenant. Adiciona a tabela `users` e uma coluna
`user_id` NULLABLE em todas as tabelas de dados existentes. É seguido pela
revisão de backfill (que preenche `user_id`, resolve duplicatas de categoria
e só então torna a coluna NOT NULL) — ver runbook no plano de implementação.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e8a74d06536e'
down_revision: Union[str, Sequence[str], None] = 'a3f8c2e01b94'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TABLES_WITH_USER_ID = [
    "payables",
    "transactions",
    "categories",
    "category_rules",
    "budgets",
    "recurring_payables",
    "bank_accounts",
    "push_subscriptions",
]


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("hashed_password", sa.String(length=1024), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("is_superuser", sa.Boolean(), nullable=False),
        sa.Column("is_verified", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_users_email"), "users", ["email"], unique=True)

    for table in _TABLES_WITH_USER_ID:
        op.add_column(table, sa.Column("user_id", sa.Uuid(), nullable=True))
        op.create_foreign_key(
            f"fk_{table}_user_id_users",
            table,
            "users",
            ["user_id"],
            ["id"],
            ondelete="CASCADE",
        )
        op.create_index(f"ix_{table}_user_id", table, ["user_id"])


def downgrade() -> None:
    for table in reversed(_TABLES_WITH_USER_ID):
        op.drop_index(f"ix_{table}_user_id", table_name=table)
        op.drop_constraint(f"fk_{table}_user_id_users", table, type_="foreignkey")
        op.drop_column(table, "user_id")

    op.drop_index(op.f("ix_users_email"), table_name="users")
    op.drop_table("users")
