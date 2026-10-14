"""decimal quantities and company settings

Revision ID: d11a0e5c4b21
Revises: c4a8e2b71f03
Create Date: 2026-10-14 18:10:00.000000

"""
from typing import Sequence, Union
from uuid import UUID

import sqlalchemy as sa
from alembic import op
from uuid6 import uuid7

revision: str = "d11a0e5c4b21"
down_revision: Union[str, Sequence[str], None] = "c4a8e2b71f03"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _qty(table: str, column: str) -> None:
    op.alter_column(
        table,
        column,
        existing_type=sa.Integer(),
        type_=sa.Numeric(14, 3),
        postgresql_using=f"{column}::numeric(14,3)",
    )


def _money(table: str, column: str, nullable: bool = False) -> None:
    op.alter_column(
        table,
        column,
        existing_type=sa.Integer(),
        type_=sa.Numeric(12, 2),
        postgresql_using=f"{column}::numeric(12,2)",
        existing_nullable=nullable,
    )


def upgrade() -> None:
    _qty("products", "quantity")
    _qty("products", "alert_quantity")
    _money("products", "sale_price_without_gst")
    _qty("raw_materials", "quantity")
    _qty("raw_materials", "alert_quantity")
    _money("raw_materials", "price")
    _qty("sales", "product_quantity")
    _qty("purchase_order_raw_materials", "quantity")
    _money("purchase_order_raw_materials", "per_unit_price")
    _qty("purchase_order_products", "quantity")
    _money("purchase_order_products", "per_unit_price")
    _qty("production_jobs", "quantity")

    op.create_table(
        "company_settings",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("company_name", sa.String(length=255), nullable=False),
        sa.Column("gstin", sa.String(length=20), nullable=False, server_default=""),
        sa.Column("state", sa.String(length=80), nullable=False, server_default=""),
        sa.Column("address", sa.Text(), nullable=False, server_default=""),
        sa.Column("delivery_charge", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("invoice_prefix", sa.String(length=16), nullable=False, server_default="INV"),
        sa.PrimaryKeyConstraint("id"),
    )
    company_id: UUID = uuid7()
    op.execute(
        sa.text(
            "INSERT INTO company_settings "
            "(id, company_name, gstin, state, address, delivery_charge, invoice_prefix) "
            "SELECT :id, 'Sai Daya Steel', '', '', '', 0, 'INV' "
            "WHERE NOT EXISTS (SELECT 1 FROM company_settings)"
        ).bindparams(id=company_id)
    )


def downgrade() -> None:
    op.drop_table("company_settings")
