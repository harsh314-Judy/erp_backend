"""purchase payments and activity log

Revision ID: c7e2a91b4d08
Revises: b0c6d3f58a74
Create Date: 2026-11-17 16:30:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "c7e2a91b4d08"
down_revision: Union[str, Sequence[str], None] = "b0c6d3f58a74"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "purchase_orders",
        sa.Column("amount_paid", sa.Numeric(12, 2), server_default="0", nullable=False),
    )
    op.create_table(
        "purchase_payments",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("purchase_order_id", sa.Uuid(), nullable=False),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("method", sa.String(length=16), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("attachment_id", sa.Uuid(), nullable=False),
        sa.Column("recorded_by_user_id", sa.Uuid(), nullable=True),
        sa.ForeignKeyConstraint(["attachment_id"], ["attachments.id"]),
        sa.ForeignKeyConstraint(["purchase_order_id"], ["purchase_orders.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["recorded_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_purchase_payments_purchase_order_id", "purchase_payments", ["purchase_order_id"])
    op.create_table(
        "activity_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("ref_type", sa.String(length=32), nullable=False),
        sa.Column("ref_id", sa.Uuid(), nullable=True),
        sa.Column("actor_user_id", sa.Uuid(), nullable=True),
        sa.Column("link", sa.String(length=255), nullable=True),
        sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_activity_events_occurred_at", "activity_events", ["occurred_at"])
    op.create_index("ix_activity_events_kind", "activity_events", ["kind"])
    op.execute(
        """
        INSERT INTO activity_events (id, created_at, updated_at, occurred_at, kind, summary, ref_type, ref_id, actor_user_id, link)
        SELECT gen_random_uuid(), p.created_at, p.created_at, p.created_at, 'payments',
               'Customer payment ' || p.amount::text || ' by ' || p.method,
               'invoice', p.invoice_id, p.recorded_by_user_id, '/accountant/payments'
        FROM payments p
        """
    )
    op.execute(
        """
        INSERT INTO activity_events (id, created_at, updated_at, occurred_at, kind, summary, ref_type, ref_id, actor_user_id, link)
        SELECT gen_random_uuid(), COALESCE(j.completed_at, j.updated_at), COALESCE(j.completed_at, j.updated_at),
               COALESCE(j.completed_at, j.updated_at), 'job_approvals',
               'Job approved · produced ' || j.produced_quantity::text,
               'production_job', j.id, NULL, '/accountant/jobs'
        FROM production_jobs j
        WHERE j.status = 'completed'
        """
    )
    op.execute(
        """
        INSERT INTO activity_events (id, created_at, updated_at, occurred_at, kind, summary, ref_type, ref_id, actor_user_id, link)
        SELECT gen_random_uuid(), o.updated_at, o.updated_at, o.updated_at, 'purchases',
               'Purchase received',
               'purchase_order', o.id, o.created_by_user_id, '/purchases'
        FROM purchase_orders o
        WHERE o.stock_received = true
        """
    )
    op.execute(
        """
        INSERT INTO activity_events (id, created_at, updated_at, occurred_at, kind, summary, ref_type, ref_id, actor_user_id, link)
        SELECT gen_random_uuid(), o.updated_at, o.updated_at, o.updated_at,
               CASE WHEN replace(o.status, ' ', '_') IN ('delivered', 'dispatched') THEN 'sold_goods' ELSE 'dispatches' END,
               'Sales order ' || o.status,
               'sales_order', o.id, NULL, '/sales'
        FROM sales_orders o
        WHERE replace(o.status, ' ', '_') IN ('in_delivery', 'delivered', 'dispatched')
        """
    )
    op.execute(
        """
        INSERT INTO activity_events (id, created_at, updated_at, occurred_at, kind, summary, ref_type, ref_id, actor_user_id, link)
        SELECT gen_random_uuid(), a.signed_in_at, a.signed_in_at, a.signed_in_at, 'attendance',
               a.person || ' signed in',
               'attendance', a.id, a.user_id, '/activity'
        FROM attendance a
        """
    )
    op.execute(
        """
        INSERT INTO activity_events (id, created_at, updated_at, occurred_at, kind, summary, ref_type, ref_id, actor_user_id, link)
        SELECT gen_random_uuid(), f.created_at, f.created_at, f.created_at, 'floor',
               'Floor entry',
               'floor_entry', f.id, f.created_by_user_id, '/departments/' || f.operation_id::text || '/now'
        FROM floor_entries f
        """
    )


def downgrade() -> None:
    op.drop_index("ix_activity_events_kind", table_name="activity_events")
    op.drop_index("ix_activity_events_occurred_at", table_name="activity_events")
    op.drop_table("activity_events")
    op.drop_index("ix_purchase_payments_purchase_order_id", table_name="purchase_payments")
    op.drop_table("purchase_payments")
    op.drop_column("purchase_orders", "amount_paid")
