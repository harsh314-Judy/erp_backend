"""purchase cancel reason

Revision ID: b3c7e65a0d43
Revises: a2b6d54f9c32
Create Date: 2026-11-18 22:45:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "b3c7e65a0d43"
down_revision: Union[str, Sequence[str], None] = "a2b6d54f9c32"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("purchase_orders", sa.Column("cancel_reason", sa.Text(), nullable=True))
    op.add_column("purchase_orders", sa.Column("status_before_cancel", sa.String(length=32), nullable=True))


def downgrade() -> None:
    op.drop_column("purchase_orders", "status_before_cancel")
    op.drop_column("purchase_orders", "cancel_reason")
