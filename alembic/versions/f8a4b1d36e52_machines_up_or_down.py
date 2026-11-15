"""machines that are up or down

Revision ID: f8a4b1d36e52
Revises: e7f3a0c25d41
Create Date: 2026-11-15 14:05:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "f8a4b1d36e52"
down_revision: Union[str, Sequence[str], None] = "e7f3a0c25d41"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "machines",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("operation_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(length=8), server_default="up", nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["operation_id"], ["operations.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_machines_operation_id", "machines", ["operation_id"])
    op.create_index("ix_machines_status", "machines", ["status"])
    op.add_column("production_job_stages", sa.Column("problem_machine_id", sa.Uuid(), nullable=True))
    op.create_foreign_key(
        "fk_production_job_stages_problem_machine_id",
        "production_job_stages",
        "machines",
        ["problem_machine_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_production_job_stages_problem_machine_id", "production_job_stages", ["problem_machine_id"])


def downgrade() -> None:
    op.drop_index("ix_production_job_stages_problem_machine_id", table_name="production_job_stages")
    op.drop_constraint(
        "fk_production_job_stages_problem_machine_id",
        "production_job_stages",
        type_="foreignkey",
    )
    op.drop_column("production_job_stages", "problem_machine_id")
    op.drop_index("ix_machines_status", table_name="machines")
    op.drop_index("ix_machines_operation_id", table_name="machines")
    op.drop_table("machines")
