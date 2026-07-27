"""add credit card bills

Revision ID: ae3884e5cebe
Revises: ed1c2a45d964
Create Date: 2026-07-27 14:09:52.459934

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'ae3884e5cebe'
down_revision: Union[str, Sequence[str], None] = 'ed1c2a45d964'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "credit_card_bills",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("bank_account_id", sa.Uuid(), nullable=False),
        sa.Column("pluggy_account_id", sa.String(length=100), nullable=False),
        sa.Column("external_id", sa.String(length=100), nullable=False),
        sa.Column("due_date", sa.Date(), nullable=False),
        sa.Column("total_amount", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("minimum_payment_amount", sa.Numeric(precision=12, scale=2), nullable=True),
        sa.Column("allows_installments", sa.Boolean(), nullable=True),
        sa.Column("payable_id", sa.Uuid(), nullable=True),
        sa.Column("synced_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["bank_account_id"], ["bank_accounts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["payable_id"], ["payables.id"], ondelete="SET NULL"),
        sa.UniqueConstraint("user_id", "external_id", name="uq_credit_card_bills_user_id_external_id"),
    )
    op.create_index("ix_credit_card_bills_user_id", "credit_card_bills", ["user_id"])
    op.create_index("ix_credit_card_bills_bank_account_id", "credit_card_bills", ["bank_account_id"])


def downgrade() -> None:
    op.drop_index("ix_credit_card_bills_bank_account_id", table_name="credit_card_bills")
    op.drop_index("ix_credit_card_bills_user_id", table_name="credit_card_bills")
    op.drop_table("credit_card_bills")
