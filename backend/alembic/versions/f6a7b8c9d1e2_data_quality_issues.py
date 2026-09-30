"""data_quality_issues

Revision ID: f6a7b8c9d1e2
Revises: e5f6a7b8c9d1
Create Date: 2026-10-01 14:00:00.000000

Suspeitas de classificação errada achadas pela auditoria (#199).
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f6a7b8c9d1e2"
down_revision: Union[str, Sequence[str], None] = "e5f6a7b8c9d1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "data_quality_issues",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("kind", sa.String(length=40), nullable=False),
        sa.Column("severity", sa.String(length=10), nullable=False),
        sa.Column("status", sa.String(length=10), nullable=False),
        sa.Column("fingerprint", sa.String(length=40), nullable=False),
        sa.Column("transaction_ids", sa.JSON(), nullable=False),
        sa.Column("detail", sa.JSON(), nullable=False),
        sa.Column("detected_at", sa.DateTime(), nullable=False),
        sa.Column("resolved_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "fingerprint", name="uq_data_quality_issues_user_fingerprint"),
    )
    op.create_index("ix_data_quality_issues_user_id", "data_quality_issues", ["user_id"])
    op.create_index(
        "ix_data_quality_issues_user_status", "data_quality_issues", ["user_id", "status"]
    )


def downgrade() -> None:
    op.drop_index("ix_data_quality_issues_user_status", table_name="data_quality_issues")
    op.drop_index("ix_data_quality_issues_user_id", table_name="data_quality_issues")
    op.drop_table("data_quality_issues")
