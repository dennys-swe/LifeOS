"""category_rules: add is_transfer

Revision ID: f9a0b1c2d3e4
Revises: e5f6a7b8c9d0
Create Date: 2026-09-17 15:00:00.000000

Regra de categoria hoje só sabe atribuir categoria — não dá pra reconhecer
que uma transferência recebida de uma pessoa específica (ex: divisão de
contas entre casal) não é receita de verdade. `is_transfer` normal só vem de
`pluggy_category_map` (categoria da Pluggy ou descrição de pagamento de
fatura), que não conhece nomes de pessoa. A regra agora pode marcar isso
também, além da categoria.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f9a0b1c2d3e4"
down_revision: Union[str, Sequence[str], None] = "e5f6a7b8c9d0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "category_rules",
        sa.Column("is_transfer", sa.Boolean(), nullable=False, server_default="false"),
    )


def downgrade() -> None:
    op.drop_column("category_rules", "is_transfer")
