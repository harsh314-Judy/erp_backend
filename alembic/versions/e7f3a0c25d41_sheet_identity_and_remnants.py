"""sheet identity, remnants, sheets taken, and receipt fail

Revision ID: e7f3a0c25d41
Revises: d6e2f9b14c30
Create Date: 2026-11-15 14:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "e7f3a0c25d41"
down_revision: Union[str, Sequence[str], None] = "d6e2f9b14c30"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("raw_materials", sa.Column("thickness", sa.String(length=32), nullable=True))
    op.add_column("raw_materials", sa.Column("grade", sa.String(length=32), nullable=True))
    op.add_column("raw_materials", sa.Column("size", sa.String(length=64), nullable=True))
    op.add_column("raw_materials", sa.Column("parent_raw_material_id", sa.Uuid(), nullable=True))
    op.add_column(
        "raw_materials",
        sa.Column("is_remnant", sa.Boolean(), server_default=sa.false(), nullable=False),
    )
    op.create_foreign_key(
        "fk_raw_materials_parent_raw_material_id",
        "raw_materials",
        "raw_materials",
        ["parent_raw_material_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "ix_raw_materials_parent_raw_material_id",
        "raw_materials",
        ["parent_raw_material_id"],
    )
    op.execute(
        "CREATE UNIQUE INDEX uq_raw_materials_remnant_size "
        "ON raw_materials (parent_raw_material_id, lower(size)) WHERE is_remnant"
    )
    op.add_column(
        "production_job_inputs",
        sa.Column("taken_quantity", sa.Numeric(14, 3), server_default="0", nullable=False),
    )
    op.add_column("purchase_orders", sa.Column("receipt_fail_reason", sa.String(length=32), nullable=True))
    op.add_column("purchase_orders", sa.Column("receipt_fail_note", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("purchase_orders", "receipt_fail_note")
    op.drop_column("purchase_orders", "receipt_fail_reason")
    op.drop_column("production_job_inputs", "taken_quantity")
    op.execute("DROP INDEX IF EXISTS uq_raw_materials_remnant_size")
    op.drop_index("ix_raw_materials_parent_raw_material_id", table_name="raw_materials")
    op.drop_constraint("fk_raw_materials_parent_raw_material_id", "raw_materials", type_="foreignkey")
    op.drop_column("raw_materials", "is_remnant")
    op.drop_column("raw_materials", "parent_raw_material_id")
    op.drop_column("raw_materials", "size")
    op.drop_column("raw_materials", "grade")
    op.drop_column("raw_materials", "thickness")
