"""index stock reservations by item and status

Revision ID: f12c8d4e5a01
Revises: e88b1a2c4d90
Create Date: 2026-10-19 18:20:00.000000

"""
from typing import Sequence, Union

from alembic import op

revision: str = "f12c8d4e5a01"
down_revision: Union[str, Sequence[str], None] = "e88b1a2c4d90"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index(
        "ix_stock_reservations_raw_material_id",
        "stock_reservations",
        ["raw_material_id"],
    )
    op.create_index(
        "ix_stock_reservations_status_material",
        "stock_reservations",
        ["status", "raw_material_id"],
    )
    op.create_index(
        "ix_stock_reservations_status_product",
        "stock_reservations",
        ["status", "product_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_stock_reservations_status_product", table_name="stock_reservations")
    op.drop_index("ix_stock_reservations_status_material", table_name="stock_reservations")
    op.drop_index("ix_stock_reservations_raw_material_id", table_name="stock_reservations")
