"""product routes, recipes, and raw material details

Revision ID: d22b1f6d5c32
Revises: d11a0e5c4b21
Create Date: 2026-10-14 18:12:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from uuid6 import uuid7

revision: str = "d22b1f6d5c32"
down_revision: Union[str, Sequence[str], None] = "d11a0e5c4b21"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_OPERATIONS = (
    ("cutting", "Cut sheet stock into the required flat shape."),
    ("shaping", "Form the flat shape into a three-dimensional product."),
    ("assembly", "Weld two or more products into one."),
    ("polishing", "Dry or wet polish. Uses polishing material."),
    ("coloring", "Optional color finish for the buyer."),
    ("packaging", "Pack finished goods by quantity or weight."),
)


def upgrade() -> None:
    op.add_column("products", sa.Column("product_type", sa.String(length=20), nullable=False, server_default="manufactured"))
    op.add_column("products", sa.Column("hsn_code", sa.String(length=16), nullable=False, server_default=""))
    op.add_column("products", sa.Column("responsible_user_id", sa.Uuid(), nullable=True))
    op.add_column("products", sa.Column("last_purchase_price", sa.Numeric(12, 2), nullable=True))
    op.create_foreign_key(
        "fk_products_responsible_user_id", "products", "users", ["responsible_user_id"], ["id"], ondelete="SET NULL"
    )
    op.create_index("ix_products_responsible_user_id", "products", ["responsible_user_id"])

    op.add_column("raw_materials", sa.Column("purchase_price", sa.Numeric(12, 2), nullable=False, server_default="0"))
    op.add_column("raw_materials", sa.Column("description", sa.Text(), nullable=True))
    op.add_column("raw_materials", sa.Column("kind", sa.String(length=32), nullable=False, server_default="sheet"))
    op.add_column("raw_materials", sa.Column("responsible_user_id", sa.Uuid(), nullable=True))
    op.create_foreign_key(
        "fk_raw_materials_responsible_user_id",
        "raw_materials",
        "users",
        ["responsible_user_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_raw_materials_responsible_user_id", "raw_materials", ["responsible_user_id"])

    op.create_table(
        "product_route_steps",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("product_id", sa.Uuid(), nullable=False),
        sa.Column("operation_id", sa.Uuid(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["operation_id"], ["operations.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_product_route_steps_product_id", "product_route_steps", ["product_id"])
    op.create_index("ix_product_route_steps_operation_id", "product_route_steps", ["operation_id"])

    op.create_table(
        "product_components",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("product_id", sa.Uuid(), nullable=False),
        sa.Column("component_product_id", sa.Uuid(), nullable=True),
        sa.Column("component_raw_material_id", sa.Uuid(), nullable=True),
        sa.Column("quantity_per_unit", sa.Numeric(14, 3), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False, server_default="0"),
        sa.ForeignKeyConstraint(["component_product_id"], ["products.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["component_raw_material_id"], ["raw_materials.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_product_components_product_id", "product_components", ["product_id"])

    for name, description in _OPERATIONS:
        op.execute(
            sa.text(
                "INSERT INTO operations (id, name, description) "
                "SELECT :id, :name, :description "
                "WHERE NOT EXISTS (SELECT 1 FROM operations WHERE name = :name)"
            ).bindparams(id=uuid7(), name=name, description=description)
        )


def downgrade() -> None:
    op.drop_table("product_components")
    op.drop_table("product_route_steps")
    op.drop_constraint("fk_raw_materials_responsible_user_id", "raw_materials", type_="foreignkey")
    op.drop_index("ix_raw_materials_responsible_user_id", table_name="raw_materials")
    op.drop_column("raw_materials", "responsible_user_id")
    op.drop_column("raw_materials", "kind")
    op.drop_column("raw_materials", "description")
    op.drop_column("raw_materials", "purchase_price")
    op.drop_constraint("fk_products_responsible_user_id", "products", type_="foreignkey")
    op.drop_index("ix_products_responsible_user_id", table_name="products")
    op.drop_column("products", "last_purchase_price")
    op.drop_column("products", "responsible_user_id")
    op.drop_column("products", "hsn_code")
    op.drop_column("products", "product_type")
