"""backfill user_id and enforce constraints

Revision ID: ed1c2a45d964
Revises: e8a74d06536e
Create Date: 2026-07-27 13:47:55.010055

Parte 2/2 da migração multi-tenant. RUNBOOK (rodar nesta ordem):

1. Deploy da revisão anterior (e8a74d06536e) + código da Fase 1.
2. O dono do sistema se registra via `POST /auth/register` (vira o primeiro
   usuário — o `on_after_register` semeia 6 categorias padrão para ele).
3. Rodar esta revisão (`alembic upgrade head`).

Esta migration assume que existe pelo menos um usuário em `users` (o dono) e
falha explicitamente se não houver. Ela:
- desduplica as categorias (o registro do dono semeou 6 categorias novas que
  colidem, por nome, com as 6 categorias globais antigas — mantém a antiga,
  que já carrega o histórico de FKs, e descarta a nova, reapontando FKs);
- preenche `user_id` de todo o histórico restante com o id do dono;
- torna `user_id` NOT NULL nas 8 tabelas;
- troca as uniques globais por uniques compostas por usuário;
- cria o índice composto usado na deduplicação de sync da Pluggy.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import text

# revision identifiers, used by Alembic.
revision: str = 'ed1c2a45d964'
down_revision: Union[str, Sequence[str], None] = 'e8a74d06536e'
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

_TABLES_WITH_CATEGORY_ID = [
    "payables",
    "transactions",
    "budgets",
    "category_rules",
    "recurring_payables",
]


def upgrade() -> None:
    bind = op.get_bind()

    owner_id = bind.execute(
        text("SELECT id FROM users ORDER BY created_at ASC LIMIT 1")
    ).scalar()

    if owner_id is None:
        raise RuntimeError(
            "Nenhum usuário encontrado em `users`. Registre o usuário dono via "
            "POST /auth/register antes de rodar esta migration — ver runbook no "
            "docstring deste arquivo."
        )

    duplicates = bind.execute(
        text(
            """
            SELECT old_cat.id AS old_id, new_cat.id AS new_id
            FROM categories AS old_cat
            JOIN categories AS new_cat
              ON new_cat.name = old_cat.name AND new_cat.user_id = :owner_id
            WHERE old_cat.user_id IS NULL
            """
        ),
        {"owner_id": owner_id},
    ).fetchall()

    for old_id, new_id in duplicates:
        for table in _TABLES_WITH_CATEGORY_ID:
            bind.execute(
                text(f"UPDATE {table} SET category_id = :old_id WHERE category_id = :new_id"),
                {"old_id": old_id, "new_id": new_id},
            )
        bind.execute(text("DELETE FROM categories WHERE id = :new_id"), {"new_id": new_id})

    for table in _TABLES_WITH_USER_ID:
        bind.execute(
            text(f"UPDATE {table} SET user_id = :owner_id WHERE user_id IS NULL"),
            {"owner_id": owner_id},
        )
        op.alter_column(table, "user_id", nullable=False)

    op.drop_constraint("categories_name_key", "categories", type_="unique")
    op.create_unique_constraint("uq_categories_user_id_name", "categories", ["user_id", "name"])

    op.drop_constraint("uq_budget_category_month_year", "budgets", type_="unique")
    op.create_unique_constraint(
        "uq_budget_user_category_month_year",
        "budgets",
        ["user_id", "category_id", "month", "year"],
    )

    op.create_index("ix_transactions_user_id_source", "transactions", ["user_id", "source"])


def downgrade() -> None:
    op.drop_index("ix_transactions_user_id_source", table_name="transactions")

    op.drop_constraint("uq_budget_user_category_month_year", "budgets", type_="unique")
    op.create_unique_constraint(
        "uq_budget_category_month_year", "budgets", ["category_id", "month", "year"]
    )

    op.drop_constraint("uq_categories_user_id_name", "categories", type_="unique")
    op.create_unique_constraint("categories_name_key", "categories", ["name"])

    for table in _TABLES_WITH_USER_ID:
        op.alter_column(table, "user_id", nullable=True)

    # Nota: as categorias duplicadas descartadas no upgrade() não são
    # recriadas — esta reversão é parcial (apenas de schema, não de dados).
