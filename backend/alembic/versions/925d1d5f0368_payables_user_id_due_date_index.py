"""payables: index (user_id, due_date)

Revision ID: 925d1d5f0368
Revises: c4d5e6f7a8b9
Create Date: 2026-09-22 18:53:01.000692

Issue #133. `Payable` só tem índice em `user_id` hoje. As consultas mais
frequentes (`list_payables`, `get_summary`, `get_history`, `suggest_pending`)
filtram por range de `due_date` além de `user_id`. Preventivo, não fix de
gargalo atual — com o volume de payables de hoje o ganho medido tende a ser
~0, mas é barato e evita ter que migrar sob pressão mais pra frente. Segue o
precedente de `b3c4d5e6f7a8` (índice composto em `transactions`).
"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "925d1d5f0368"
down_revision: Union[str, Sequence[str], None] = "c4d5e6f7a8b9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index("ix_payables_user_id_due_date", "payables", ["user_id", "due_date"])


def downgrade() -> None:
    op.drop_index("ix_payables_user_id_due_date", table_name="payables")
