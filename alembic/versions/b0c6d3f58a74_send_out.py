"""route send-out flag and outside send rows

Revision ID: b0c6d3f58a74
Revises: a9b5c2e47f63
Create Date: 2026-11-15 15:12:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "b0c6d3f58a74"
down_revision: Union[str, Sequence[str], None] = "a9b5c2e47f63"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "product_route_steps",
        sa.Column("allows_send_out", sa.Boolean(), server_default=sa.false(), nullable=False),
    )
    op.add_column(
        "product_route_steps",
        sa.Column("standard_scrap_percent", sa.Numeric(6, 2), nullable=True),
    )
    op.add_column(
        "production_job_stages",
        sa.Column("allows_send_out", sa.Boolean(), server_default=sa.false(), nullable=False),
    )
    op.add_column(
        "production_job_stages",
        sa.Column("standard_scrap_percent", sa.Numeric(6, 2), nullable=True),
    )
    op.create_table(
        "stage_sends",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("stage_id", sa.Uuid(), nullable=False),
        sa.Column("job_id", sa.Uuid(), nullable=False),
        sa.Column("supplier_id", sa.Uuid(), nullable=False),
        sa.Column("quantity", sa.Numeric(14, 3), nullable=False),
        sa.Column("sent_on", sa.Date(), nullable=False),
        sa.Column("good_quantity", sa.Numeric(14, 3), server_default="0", nullable=False),
        sa.Column("rejected_quantity", sa.Numeric(14, 3), server_default="0", nullable=False),
        sa.ForeignKeyConstraint(["stage_id"], ["production_job_stages.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["job_id"], ["production_jobs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["supplier_id"], ["suppliers.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_stage_sends_stage_id", "stage_sends", ["stage_id"])
    op.create_index("ix_stage_sends_job_id", "stage_sends", ["job_id"])
    op.create_index("ix_stage_sends_supplier_id", "stage_sends", ["supplier_id"])


def downgrade() -> None:
    op.drop_index("ix_stage_sends_supplier_id", table_name="stage_sends")
    op.drop_index("ix_stage_sends_job_id", table_name="stage_sends")
    op.drop_index("ix_stage_sends_stage_id", table_name="stage_sends")
    op.drop_table("stage_sends")
    op.drop_column("production_job_stages", "standard_scrap_percent")
    op.drop_column("production_job_stages", "allows_send_out")
    op.drop_column("product_route_steps", "standard_scrap_percent")
    op.drop_column("product_route_steps", "allows_send_out")
