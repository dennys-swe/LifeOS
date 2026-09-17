"""transactions: unique(user_id, source)

Revision ID: e5f6a7b8c9d0
Revises: d1e2f3a4b5c6
Create Date: 2026-09-17 13:00:00.000000

Rede de segurança da issue #8: o dedup do sync (bank_sync_service) passou a
checar duplicata em memória em vez de um SELECT por transação — a unicidade
de (user_id, source) nunca foi imposta pelo banco (só um índice), então essa
constraint é a garantia de verdade contra uma corrida (dois syncs da mesma
conta em paralelo) ou um bug futuro que reintroduza um INSERT duplicado.

Confirmado antes de escrever esta migration (produção, 2026-09-17, leitura):
zero linhas com (user_id, source) duplicado em `transactions` — não deveria
falhar em nenhum ambiente com dados existentes.
"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e5f6a7b8c9d0"
down_revision: Union[str, Sequence[str], None] = "d1e2f3a4b5c6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_index("ix_transactions_user_id_source", table_name="transactions")
    op.create_unique_constraint(
        "uq_transactions_user_id_source", "transactions", ["user_id", "source"]
    )


def downgrade() -> None:
    op.drop_constraint("uq_transactions_user_id_source", "transactions", type_="unique")
    op.create_index(
        "ix_transactions_user_id_source", "transactions", ["user_id", "source"]
    )
