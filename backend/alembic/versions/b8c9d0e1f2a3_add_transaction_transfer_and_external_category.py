"""add transactions.is_transfer and transactions.external_category

Duas colunas para corrigir a classificação das transações importadas da Pluggy:

- `external_category`: a categoria que a Pluggy já atribui ("Groceries", "Gas
  stations", "Credit card payment"...). Era ignorada pelo sync, então 100% das
  transações ficavam sem categoria embora 96% viessem classificadas da API.
  Guardar o valor cru permite re-mapear depois sem re-consultar a API.

- `is_transfer`: marca dinheiro que só muda de lugar (quitação de fatura,
  transferência entre as próprias contas, aporte em investimento). Excluído dos
  totais de gasto — sem isso a mesma grana conta duas vezes (a compra no cartão
  E a quitação da fatura).

O backfill das linhas existentes NÃO é feito aqui: depende de re-consultar a
Pluggy para descobrir a categoria e o `type` de cada transação já gravada (o
default `false`/`NULL` deixa as linhas antigas num estado neutro e explícito).

Revision ID: b8c9d0e1f2a3
Revises: a7b8c9d0e1f2
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "b8c9d0e1f2a3"
down_revision: Union[str, Sequence[str], None] = "a7b8c9d0e1f2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "transactions",
        sa.Column(
            "is_transfer",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )
    op.add_column(
        "transactions",
        sa.Column("external_category", sa.String(length=80), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("transactions", "external_category")
    op.drop_column("transactions", "is_transfer")
