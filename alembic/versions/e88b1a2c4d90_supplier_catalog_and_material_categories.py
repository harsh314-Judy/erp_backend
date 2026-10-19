"""supplier catalog, material categories, and purchase receipt flag

Revision ID: e88b1a2c4d90
Revises: d7706eb2a187
Create Date: 2026-10-19 18:10:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "e88b1a2c4d90"
down_revision: Union[str, Sequence[str], None] = "d7706eb2a187"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "raw_material_categories",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("name", sa.String(length=150), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )
    op.create_index("ix_raw_material_categories_name", "raw_material_categories", ["name"])
    op.add_column("suppliers", sa.Column("supply_kind", sa.String(length=16), nullable=False, server_default="both"))
    op.add_column("raw_materials", sa.Column("category_id", sa.Uuid(), nullable=True))
    op.add_column("raw_materials", sa.Column("supplier_id", sa.Uuid(), nullable=True))
    op.create_foreign_key(
        "fk_raw_materials_category_id",
        "raw_materials",
        "raw_material_categories",
        ["category_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_foreign_key(
        "fk_raw_materials_supplier_id",
        "raw_materials",
        "suppliers",
        ["supplier_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_raw_materials_category_id", "raw_materials", ["category_id"])
    op.create_index("ix_raw_materials_supplier_id", "raw_materials", ["supplier_id"])
    op.add_column(
        "purchase_orders",
        sa.Column("stock_received", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.execute("UPDATE purchase_orders SET stock_received = true WHERE status = 'verified'")


def downgrade() -> None:
    op.drop_column("purchase_orders", "stock_received")
    op.drop_index("ix_raw_materials_supplier_id", table_name="raw_materials")
    op.drop_index("ix_raw_materials_category_id", table_name="raw_materials")
    op.drop_constraint("fk_raw_materials_supplier_id", "raw_materials", type_="foreignkey")
    op.drop_constraint("fk_raw_materials_category_id", "raw_materials", type_="foreignkey")
    op.drop_column("raw_materials", "supplier_id")
    op.drop_column("raw_materials", "category_id")
    op.drop_column("suppliers", "supply_kind")
    op.drop_index("ix_raw_material_categories_name", table_name="raw_material_categories")
    op.drop_table("raw_material_categories")
