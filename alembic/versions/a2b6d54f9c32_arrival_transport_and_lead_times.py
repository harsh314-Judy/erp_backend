"""arrival transport and sales lead times

Revision ID: a2b6d54f9c32
Revises: f1a5c43e8b21
Create Date: 2026-11-18 22:10:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "a2b6d54f9c32"
down_revision: Union[str, Sequence[str], None] = "f1a5c43e8b21"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("purchase_orders", sa.Column("transport_mode", sa.String(length=16), nullable=True))
    op.add_column("purchase_orders", sa.Column("driver_name", sa.String(length=120), nullable=True))
    op.add_column("purchase_orders", sa.Column("carrier_phone", sa.String(length=32), nullable=True))
    op.add_column("purchase_orders", sa.Column("pickup_user_id", sa.Uuid(), nullable=True))
    op.create_foreign_key(
        "fk_purchase_orders_pickup_user_id",
        "purchase_orders",
        "users",
        ["pickup_user_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.add_column("products", sa.Column("make_days", sa.Integer(), nullable=False, server_default="7"))
    op.add_column("products", sa.Column("buy_days", sa.Integer(), nullable=False, server_default="7"))
    op.add_column("products", sa.Column("ship_days", sa.Integer(), nullable=False, server_default="2"))
    op.add_column("products", sa.Column("buffer_days", sa.Integer(), nullable=False, server_default="2"))
    op.add_column("sales_orders", sa.Column("transport_mode", sa.String(length=16), nullable=True))
    op.add_column("sales_orders", sa.Column("driver_name", sa.String(length=120), nullable=True))
    op.add_column("sales_orders", sa.Column("carrier_phone", sa.String(length=32), nullable=True))
    op.add_column("sales_orders", sa.Column("vehicle_plate", sa.String(length=20), nullable=True))
    op.add_column("sales_orders", sa.Column("pickup_user_id", sa.Uuid(), nullable=True))
    op.add_column("sales_orders", sa.Column("receipt_attachment_id", sa.Uuid(), nullable=True))
    op.create_foreign_key(
        "fk_sales_orders_pickup_user_id",
        "sales_orders",
        "users",
        ["pickup_user_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.add_column("sales_order_lines", sa.Column("custom_unit", sa.String(length=40), nullable=True))
    op.add_column("sales_order_lines", sa.Column("gst", sa.Boolean(), nullable=False, server_default=sa.true()))


def downgrade() -> None:
    op.drop_column("sales_order_lines", "gst")
    op.drop_column("sales_order_lines", "custom_unit")
    op.drop_constraint("fk_sales_orders_pickup_user_id", "sales_orders", type_="foreignkey")
    op.drop_column("sales_orders", "receipt_attachment_id")
    op.drop_column("sales_orders", "pickup_user_id")
    op.drop_column("sales_orders", "vehicle_plate")
    op.drop_column("sales_orders", "carrier_phone")
    op.drop_column("sales_orders", "driver_name")
    op.drop_column("sales_orders", "transport_mode")
    op.drop_column("products", "buffer_days")
    op.drop_column("products", "ship_days")
    op.drop_column("products", "buy_days")
    op.drop_column("products", "make_days")
    op.drop_constraint("fk_purchase_orders_pickup_user_id", "purchase_orders", type_="foreignkey")
    op.drop_column("purchase_orders", "pickup_user_id")
    op.drop_column("purchase_orders", "carrier_phone")
    op.drop_column("purchase_orders", "driver_name")
    op.drop_column("purchase_orders", "transport_mode")
