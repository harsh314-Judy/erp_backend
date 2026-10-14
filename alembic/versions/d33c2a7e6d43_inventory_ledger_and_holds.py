"""inventory ledger, holds, and stock requests

Revision ID: d33c2a7e6d43
Revises: d22b1f6d5c32
Create Date: 2026-10-14 18:14:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "d33c2a7e6d43"
down_revision: Union[str, Sequence[str], None] = "d22b1f6d5c32"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _stamp() -> list[sa.Column]:
    return [
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    ]


def upgrade() -> None:
    op.create_table(
        "inventory_movements",
        *_stamp(),
        sa.Column("product_id", sa.Uuid(), nullable=True),
        sa.Column("raw_material_id", sa.Uuid(), nullable=True),
        sa.Column("quantity", sa.Numeric(14, 3), nullable=False),
        sa.Column("reason", sa.String(length=32), nullable=False),
        sa.Column("source_type", sa.String(length=32), nullable=False),
        sa.Column("source_id", sa.Uuid(), nullable=True),
        sa.Column("user_id", sa.Uuid(), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["raw_material_id"], ["raw_materials.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_inventory_movements_product_id", "inventory_movements", ["product_id"])
    op.create_index("ix_inventory_movements_raw_material_id", "inventory_movements", ["raw_material_id"])
    op.create_index("ix_inventory_movements_user_id", "inventory_movements", ["user_id"])
    op.create_index("ix_inventory_movements_reason", "inventory_movements", ["reason"])

    op.create_table(
        "stock_reservations",
        *_stamp(),
        sa.Column("product_id", sa.Uuid(), nullable=True),
        sa.Column("raw_material_id", sa.Uuid(), nullable=True),
        sa.Column("quantity", sa.Numeric(14, 3), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="held"),
        sa.Column("source_type", sa.String(length=32), nullable=False),
        sa.Column("source_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["raw_material_id"], ["raw_materials.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_stock_reservations_status", "stock_reservations", ["status"])
    op.create_index("ix_stock_reservations_source_id", "stock_reservations", ["source_id"])
    op.create_index("ix_stock_reservations_product_id", "stock_reservations", ["product_id"])

    op.create_table(
        "stock_requests",
        *_stamp(),
        sa.Column("product_id", sa.Uuid(), nullable=True),
        sa.Column("raw_material_id", sa.Uuid(), nullable=True),
        sa.Column("quantity", sa.Numeric(14, 3), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="open"),
        sa.Column("requested_by_user_id", sa.Uuid(), nullable=True),
        sa.Column("responsible_user_id", sa.Uuid(), nullable=True),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["raw_material_id"], ["raw_materials.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["requested_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["responsible_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_stock_requests_status", "stock_requests", ["status"])
    op.create_index("ix_stock_requests_responsible_user_id", "stock_requests", ["responsible_user_id"])


def downgrade() -> None:
    op.drop_table("stock_requests")
    op.drop_table("stock_reservations")
    op.drop_table("inventory_movements")
