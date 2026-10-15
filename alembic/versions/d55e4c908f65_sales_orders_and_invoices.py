"""sales orders and gst invoices

Revision ID: d55e4c908f65
Revises: d44d3b8f7e54
Create Date: 2026-10-14 18:18:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "d55e4c908f65"
down_revision: Union[str, Sequence[str], None] = "d44d3b8f7e54"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _stamp() -> list[sa.Column]:
    return [
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    ]


def upgrade() -> None:
    op.add_column("customers", sa.Column("state", sa.String(length=80), nullable=False, server_default=""))
    op.add_column("customers", sa.Column("whatsapp_mode", sa.String(length=20), nullable=False, server_default="main"))

    op.create_table(
        "sales_orders",
        *_stamp(),
        sa.Column("customer_id", sa.Uuid(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="open"),
        sa.Column("packaging_user_id", sa.Uuid(), nullable=True),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=True),
        sa.Column("delivery_charge", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["customer_id"], ["customers.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["packaging_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_sales_orders_customer_id", "sales_orders", ["customer_id"])
    op.create_index("ix_sales_orders_status", "sales_orders", ["status"])

    op.create_table(
        "sales_order_lines",
        *_stamp(),
        sa.Column("sales_order_id", sa.Uuid(), nullable=False),
        sa.Column("product_id", sa.Uuid(), nullable=False),
        sa.Column("quantity", sa.Numeric(14, 3), nullable=False),
        sa.Column("held_quantity", sa.Numeric(14, 3), nullable=False, server_default="0"),
        sa.Column("unit_price", sa.Numeric(12, 2), nullable=False),
        sa.Column("shortfall_choice", sa.String(length=16), nullable=True),
        sa.Column("reservation_id", sa.Uuid(), nullable=True),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["sales_order_id"], ["sales_orders.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_sales_order_lines_sales_order_id", "sales_order_lines", ["sales_order_id"])
    op.create_index("ix_sales_order_lines_product_id", "sales_order_lines", ["product_id"])

    op.create_table(
        "invoice_sequences",
        *_stamp(),
        sa.Column("financial_year", sa.String(length=9), nullable=False),
        sa.Column("last_number", sa.Integer(), nullable=False, server_default="0"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("financial_year"),
    )
    op.create_table(
        "invoices",
        *_stamp(),
        sa.Column("sales_order_id", sa.Uuid(), nullable=False),
        sa.Column("customer_id", sa.Uuid(), nullable=False),
        sa.Column("number", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="unpaid"),
        sa.Column("same_state", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("taxable_amount", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("cgst_amount", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("sgst_amount", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("igst_amount", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("delivery_charge", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("total_amount", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("amount_paid", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.ForeignKeyConstraint(["customer_id"], ["customers.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["sales_order_id"], ["sales_orders.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("number"),
        sa.UniqueConstraint("sales_order_id"),
    )
    op.create_index("ix_invoices_customer_id", "invoices", ["customer_id"])
    op.create_index("ix_invoices_status", "invoices", ["status"])
    op.create_table(
        "invoice_lines",
        *_stamp(),
        sa.Column("invoice_id", sa.Uuid(), nullable=False),
        sa.Column("product_id", sa.Uuid(), nullable=False),
        sa.Column("description", sa.String(length=255), nullable=False),
        sa.Column("hsn_code", sa.String(length=16), nullable=False, server_default=""),
        sa.Column("quantity", sa.Numeric(14, 3), nullable=False),
        sa.Column("unit_price", sa.Numeric(12, 2), nullable=False),
        sa.Column("gst_rate", sa.Numeric(5, 2), nullable=False, server_default="0"),
        sa.Column("taxable_amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("cgst_amount", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("sgst_amount", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("igst_amount", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.ForeignKeyConstraint(["invoice_id"], ["invoices.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_invoice_lines_invoice_id", "invoice_lines", ["invoice_id"])
    op.create_table(
        "payments",
        *_stamp(),
        sa.Column("invoice_id", sa.Uuid(), nullable=False),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("method", sa.String(length=16), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("attachment_id", sa.Uuid(), nullable=True),
        sa.Column("recorded_by_user_id", sa.Uuid(), nullable=True),
        sa.ForeignKeyConstraint(["invoice_id"], ["invoices.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["recorded_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_payments_invoice_id", "payments", ["invoice_id"])


def downgrade() -> None:
    op.drop_table("payments")
    op.drop_table("invoice_lines")
    op.drop_table("invoices")
    op.drop_table("invoice_sequences")
    op.drop_table("sales_order_lines")
    op.drop_table("sales_orders")
    op.drop_column("customers", "whatsapp_mode")
    op.drop_column("customers", "state")
