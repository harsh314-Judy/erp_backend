"""daily break allowance

Revision ID: b2c8d4e0f5a1
Revises: a1b7c3d9e4f0
Create Date: 2026-10-22 01:10:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "b2c8d4e0f5a1"
down_revision: Union[str, Sequence[str], None] = "a1b7c3d9e4f0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("daily_break_minutes", sa.Integer(), nullable=True))
    op.add_column(
        "staff_presence",
        sa.Column("break_used_seconds", sa.Integer(), server_default="0", nullable=False),
    )
    op.add_column("staff_presence", sa.Column("break_day", sa.Date(), nullable=True))


def downgrade() -> None:
    op.drop_column("staff_presence", "break_day")
    op.drop_column("staff_presence", "break_used_seconds")
    op.drop_column("users", "daily_break_minutes")
