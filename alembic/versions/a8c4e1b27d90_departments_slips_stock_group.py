"""department workers, purchase slips, raw material stock group

Revision ID: a8c4e1b27d90
Revises: e7a1c4b92d10
Create Date: 2026-11-04 13:40:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "a8c4e1b27d90"
down_revision: Union[str, Sequence[str], None] = "e7a1c4b92d10"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "department_workers",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("operation_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.ForeignKeyConstraint(["operation_id"], ["operations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("operation_id", "name", name="uq_department_worker_name"),
    )
    op.create_index("ix_department_workers_operation_id", "department_workers", ["operation_id"])
    op.add_column("production_job_stages", sa.Column("worker_id", sa.Uuid(), nullable=True))
    op.add_column("production_job_stages", sa.Column("worker_name", sa.String(length=120), nullable=True))
    op.create_foreign_key(
        "fk_production_job_stages_worker_id",
        "production_job_stages",
        "department_workers",
        ["worker_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_production_job_stages_worker_id", "production_job_stages", ["worker_id"])
    op.create_table(
        "purchase_order_attachments",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("purchase_order_id", sa.Uuid(), nullable=False),
        sa.Column("attachment_id", sa.Uuid(), nullable=False),
        sa.Column("kind", sa.String(length=24), nullable=False),
        sa.ForeignKeyConstraint(["purchase_order_id"], ["purchase_orders.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["attachment_id"], ["attachments.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_purchase_order_attachments_purchase_order_id",
        "purchase_order_attachments",
        ["purchase_order_id"],
    )
    op.add_column(
        "raw_materials",
        sa.Column("stock_group", sa.String(length=16), server_default="core", nullable=False),
    )


def downgrade() -> None:
    op.drop_column("raw_materials", "stock_group")
    op.drop_index("ix_purchase_order_attachments_purchase_order_id", table_name="purchase_order_attachments")
    op.drop_table("purchase_order_attachments")
    op.drop_index("ix_production_job_stages_worker_id", table_name="production_job_stages")
    op.drop_constraint("fk_production_job_stages_worker_id", "production_job_stages", type_="foreignkey")
    op.drop_column("production_job_stages", "worker_name")
    op.drop_column("production_job_stages", "worker_id")
    op.drop_index("ix_department_workers_operation_id", table_name="department_workers")
    op.drop_table("department_workers")
