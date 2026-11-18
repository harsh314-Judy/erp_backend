"""purchase line unit, rates, and gst

Revision ID: f1a5c43e8b21
Revises: e9b4c32d7a10
Create Date: 2026-11-18 15:20:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "f1a5c43e8b21"
down_revision: Union[str, Sequence[str], None] = "e9b4c32d7a10"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("purchase_order_lines", sa.Column("purchase_rate", sa.Numeric(12, 2), nullable=True))
    op.add_column("purchase_order_lines", sa.Column("selling_rate", sa.Numeric(12, 2), nullable=True))
    op.add_column(
        "purchase_order_lines",
        sa.Column("gst", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column(
        "purchase_order_lines",
        sa.Column("gst_percent", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column("purchase_order_lines", sa.Column("measurement_unit_id", sa.Uuid(), nullable=True))
    op.create_foreign_key(
        "fk_purchase_order_lines_measurement_unit_id",
        "purchase_order_lines",
        "measurement_units",
        ["measurement_unit_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.execute("UPDATE purchase_order_lines SET purchase_rate = unit_price WHERE purchase_rate IS NULL")


def downgrade() -> None:
    op.drop_constraint("fk_purchase_order_lines_measurement_unit_id", "purchase_order_lines", type_="foreignkey")
    op.drop_column("purchase_order_lines", "measurement_unit_id")
    op.drop_column("purchase_order_lines", "gst_percent")
    op.drop_column("purchase_order_lines", "gst")
    op.drop_column("purchase_order_lines", "selling_rate")
    op.drop_column("purchase_order_lines", "purchase_rate")
