"""attendance replaces activity and breaks

Revision ID: c3e1a9b4d2f6
Revises: b2c8d4e0f5a1
Create Date: 2026-10-26 14:40:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "c3e1a9b4d2f6"
down_revision: Union[str, Sequence[str], None] = "b2c8d4e0f5a1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "attendance",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=True),
        sa.Column("person", sa.String(length=160), nullable=False),
        sa.Column("role_name", sa.String(length=32), nullable=False),
        sa.Column("signed_in_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("signed_out_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_attendance_user_id", "attendance", ["user_id"])
    op.create_index("ix_attendance_signed_in", "attendance", ["signed_in_at"])
    op.drop_index("ix_activity_logs_role_created", table_name="activity_logs")
    op.drop_index("ix_activity_logs_user_id", table_name="activity_logs")
    op.drop_index("ix_activity_logs_created_at", table_name="activity_logs")
    op.drop_index("ix_activity_logs_role_name", table_name="activity_logs")
    op.drop_table("activity_logs")
    op.drop_table("staff_presence")
    op.drop_column("users", "daily_break_minutes")


def downgrade() -> None:
    op.add_column("users", sa.Column("daily_break_minutes", sa.Integer(), nullable=True))
    op.create_table(
        "staff_presence",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("on_break", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("break_started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("device_label", sa.String(length=120), nullable=True),
        sa.Column("break_used_seconds", sa.Integer(), server_default="0", nullable=False),
        sa.Column("break_day", sa.Date(), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("user_id"),
    )
    op.create_table(
        "activity_logs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=True),
        sa.Column("person", sa.String(length=160), nullable=False),
        sa.Column("role_name", sa.String(length=32), nullable=False),
        sa.Column("action", sa.String(length=32), nullable=False),
        sa.Column("summary", sa.String(length=160), nullable=False),
        sa.Column("ip", sa.String(length=45), nullable=True),
        sa.Column("browser", sa.String(length=48), nullable=True),
        sa.Column("os_name", sa.String(length=48), nullable=True),
        sa.Column("device_type", sa.String(length=16), nullable=True),
        sa.Column("device_model", sa.String(length=80), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_activity_logs_role_name", "activity_logs", ["role_name"])
    op.create_index("ix_activity_logs_created_at", "activity_logs", ["created_at"])
    op.create_index("ix_activity_logs_user_id", "activity_logs", ["user_id"])
    op.create_index("ix_activity_logs_role_created", "activity_logs", ["role_name", "created_at"])
    op.drop_index("ix_attendance_signed_in", table_name="attendance")
    op.drop_index("ix_attendance_user_id", table_name="attendance")
    op.drop_table("attendance")
