"""customer, supplier, sales and challan fields from the meeting addendum

Revision ID: b3e9c2a14f70
Revises: a8c4e1b27d90
Create Date: 2026-11-04 14:10:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "b3e9c2a14f70"
down_revision: Union[str, Sequence[str], None] = "a8c4e1b27d90"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("customers", sa.Column("contact_person_name", sa.String(length=150), nullable=True))
    op.add_column("suppliers", sa.Column("state", sa.String(length=80), server_default="", nullable=False))
    op.add_column("suppliers", sa.Column("payment_terms", sa.String(length=120), nullable=True))
    op.add_column("sales_orders", sa.Column("dispatch_by", sa.DateTime(timezone=True), nullable=True))
    op.add_column("sales_orders", sa.Column("turnaround_days", sa.Integer(), nullable=True))
    op.add_column("sales_orders", sa.Column("gst_billing", sa.Boolean(), server_default=sa.text("true"), nullable=False))
    op.add_column("sales_order_lines", sa.Column("source_purchase_order_id", sa.Uuid(), nullable=True))
    op.create_foreign_key(
        "fk_sales_order_lines_source_purchase_order_id",
        "sales_order_lines",
        "purchase_orders",
        ["source_purchase_order_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.add_column("purchase_orders", sa.Column("challan_number", sa.String(length=80), nullable=True))
    op.add_column("purchase_orders", sa.Column("challan_note", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("purchase_orders", "challan_note")
    op.drop_column("purchase_orders", "challan_number")
    op.drop_constraint("fk_sales_order_lines_source_purchase_order_id", "sales_order_lines", type_="foreignkey")
    op.drop_column("sales_order_lines", "source_purchase_order_id")
    op.drop_column("sales_orders", "gst_billing")
    op.drop_column("sales_orders", "turnaround_days")
    op.drop_column("sales_orders", "dispatch_by")
    op.drop_column("suppliers", "payment_terms")
    op.drop_column("suppliers", "state")
    op.drop_column("customers", "contact_person_name")
