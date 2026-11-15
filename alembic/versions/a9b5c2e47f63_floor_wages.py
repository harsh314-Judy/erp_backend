"""floor wages, attendance marks, and one already-given amount

Revision ID: a9b5c2e47f63
Revises: f8a4b1d36e52
Create Date: 2026-11-15 15:10:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "a9b5c2e47f63"
down_revision: Union[str, Sequence[str], None] = "f8a4b1d36e52"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "department_workers",
        sa.Column("wage_kind", sa.String(length=16), server_default="daily", nullable=False),
    )
    op.add_column(
        "department_workers",
        sa.Column("wage_amount", sa.Numeric(12, 2), server_default="0", nullable=False),
    )
    op.create_table(
        "floor_days",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("worker_id", sa.Uuid(), nullable=False),
        sa.Column("work_date", sa.Date(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.ForeignKeyConstraint(["worker_id"], ["department_workers.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("worker_id", "work_date", name="uq_floor_day"),
    )
    op.create_index("ix_floor_days_worker_id", "floor_days", ["worker_id"])
    op.create_table(
        "worker_month_pay",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("worker_id", sa.Uuid(), nullable=False),
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column("month", sa.Integer(), nullable=False),
        sa.Column("already_given", sa.Numeric(12, 2), server_default="0", nullable=False),
        sa.ForeignKeyConstraint(["worker_id"], ["department_workers.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("worker_id", "year", "month", name="uq_worker_month_pay"),
    )
    op.create_index("ix_worker_month_pay_worker_id", "worker_month_pay", ["worker_id"])


def downgrade() -> None:
    op.drop_index("ix_worker_month_pay_worker_id", table_name="worker_month_pay")
    op.drop_table("worker_month_pay")
    op.drop_index("ix_floor_days_worker_id", table_name="floor_days")
    op.drop_table("floor_days")
    op.drop_column("department_workers", "wage_amount")
    op.drop_column("department_workers", "wage_kind")
