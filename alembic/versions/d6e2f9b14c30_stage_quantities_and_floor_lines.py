"""stage good, scrap, and problem, and many floor lines per stage

Revision ID: d6e2f9b14c30
Revises: c5d1e8a03b21
Create Date: 2026-11-15 13:20:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "d6e2f9b14c30"
down_revision: Union[str, Sequence[str], None] = "c5d1e8a03b21"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "production_job_stages",
        sa.Column("good_quantity", sa.Numeric(14, 3), server_default="0", nullable=False),
    )
    op.add_column(
        "production_job_stages",
        sa.Column("scrap_quantity", sa.Numeric(14, 3), server_default="0", nullable=False),
    )
    op.add_column("production_job_stages", sa.Column("problem_reason", sa.String(length=64), nullable=True))
    op.add_column("production_job_stages", sa.Column("problem_note", sa.Text(), nullable=True))
    op.add_column(
        "production_job_stages",
        sa.Column("problem_opened_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column("production_job_stages", sa.Column("first_piece_ok", sa.Boolean(), nullable=True))
    op.drop_constraint("uq_floor_entries_stage_id", "floor_entries", type_="unique")
    op.create_index("ix_floor_entries_stage_id", "floor_entries", ["stage_id"])


def downgrade() -> None:
    op.drop_index("ix_floor_entries_stage_id", table_name="floor_entries")
    op.create_unique_constraint("uq_floor_entries_stage_id", "floor_entries", ["stage_id"])
    op.drop_column("production_job_stages", "first_piece_ok")
    op.drop_column("production_job_stages", "problem_opened_at")
    op.drop_column("production_job_stages", "problem_note")
    op.drop_column("production_job_stages", "problem_reason")
    op.drop_column("production_job_stages", "scrap_quantity")
    op.drop_column("production_job_stages", "good_quantity")
