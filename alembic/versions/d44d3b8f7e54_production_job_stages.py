"""production job stages and inputs

Revision ID: d44d3b8f7e54
Revises: d33c2a7e6d43
Create Date: 2026-10-14 18:16:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "d44d3b8f7e54"
down_revision: Union[str, Sequence[str], None] = "d33c2a7e6d43"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("production_jobs", sa.Column("status", sa.String(length=32), nullable=False, server_default="pending"))
    op.add_column("production_jobs", sa.Column("estimated_minutes", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("production_jobs", sa.Column("due_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("production_jobs", sa.Column("started_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("production_jobs", sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("production_jobs", sa.Column("source", sa.String(length=32), nullable=False, server_default="manual"))
    op.add_column("production_jobs", sa.Column("source_id", sa.Uuid(), nullable=True))
    op.add_column("production_jobs", sa.Column("created_by_user_id", sa.Uuid(), nullable=True))
    op.add_column("production_jobs", sa.Column("cancellation_reason", sa.Text(), nullable=True))
    op.add_column(
        "production_jobs",
        sa.Column("produced_quantity", sa.Numeric(14, 3), nullable=False, server_default="0"),
    )
    op.create_foreign_key(
        "fk_production_jobs_created_by", "production_jobs", "users", ["created_by_user_id"], ["id"], ondelete="SET NULL"
    )
    op.create_index("ix_production_jobs_status", "production_jobs", ["status"])
    op.create_index("ix_production_jobs_source_id", "production_jobs", ["source_id"])

    op.create_table(
        "production_job_stages",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("job_id", sa.Uuid(), nullable=False),
        sa.Column("operation_id", sa.Uuid(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("assigned_user_id", sa.Uuid(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="pending"),
        sa.Column("polish_type", sa.String(length=16), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["assigned_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["job_id"], ["production_jobs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["operation_id"], ["operations.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_production_job_stages_job_id", "production_job_stages", ["job_id"])
    op.create_index("ix_production_job_stages_assigned_user_id", "production_job_stages", ["assigned_user_id"])

    op.create_table(
        "production_job_inputs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("job_id", sa.Uuid(), nullable=False),
        sa.Column("product_id", sa.Uuid(), nullable=True),
        sa.Column("raw_material_id", sa.Uuid(), nullable=True),
        sa.Column("planned_quantity", sa.Numeric(14, 3), nullable=False),
        sa.Column("actual_quantity", sa.Numeric(14, 3), nullable=True),
        sa.Column("wastage_quantity", sa.Numeric(14, 3), nullable=False, server_default="0"),
        sa.Column("reservation_id", sa.Uuid(), nullable=True),
        sa.ForeignKeyConstraint(["job_id"], ["production_jobs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["raw_material_id"], ["raw_materials.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_production_job_inputs_job_id", "production_job_inputs", ["job_id"])


def downgrade() -> None:
    op.drop_table("production_job_inputs")
    op.drop_table("production_job_stages")
    op.drop_constraint("fk_production_jobs_created_by", "production_jobs", type_="foreignkey")
    op.drop_column("production_jobs", "produced_quantity")
    op.drop_column("production_jobs", "cancellation_reason")
    op.drop_column("production_jobs", "created_by_user_id")
    op.drop_column("production_jobs", "source_id")
    op.drop_column("production_jobs", "source")
    op.drop_column("production_jobs", "completed_at")
    op.drop_column("production_jobs", "started_at")
    op.drop_column("production_jobs", "due_at")
    op.drop_column("production_jobs", "estimated_minutes")
    op.drop_column("production_jobs", "status")
