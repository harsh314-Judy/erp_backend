from decimal import Decimal
from uuid import UUID

from sqlalchemy import Numeric, Text
from sqlmodel import Field

from app.db.base import Entity


class InvoiceSequence(Entity, table=True):
    __tablename__ = "invoice_sequences"

    financial_year: str = Field(max_length=9, unique=True, nullable=False, index=True)
    last_number: int = Field(default=0, nullable=False)


class Invoice(Entity, table=True):
    __tablename__ = "invoices"

    sales_order_id: UUID = Field(
        foreign_key="sales_orders.id", nullable=False, unique=True, index=True, ondelete="RESTRICT"
    )
    customer_id: UUID = Field(
        foreign_key="customers.id", nullable=False, index=True, ondelete="RESTRICT"
    )
    number: str = Field(max_length=32, unique=True, nullable=False, index=True)
    status: str = Field(default="unpaid", max_length=16, nullable=False, index=True)
    same_state: bool = Field(default=True, nullable=False)
    taxable_amount: Decimal = Field(default=Decimal("0"), sa_type=Numeric(12, 2), nullable=False)
    cgst_amount: Decimal = Field(default=Decimal("0"), sa_type=Numeric(12, 2), nullable=False)
    sgst_amount: Decimal = Field(default=Decimal("0"), sa_type=Numeric(12, 2), nullable=False)
    igst_amount: Decimal = Field(default=Decimal("0"), sa_type=Numeric(12, 2), nullable=False)
    delivery_charge: Decimal = Field(default=Decimal("0"), sa_type=Numeric(12, 2), nullable=False)
    total_amount: Decimal = Field(default=Decimal("0"), sa_type=Numeric(12, 2), nullable=False)
    amount_paid: Decimal = Field(default=Decimal("0"), sa_type=Numeric(12, 2), nullable=False)
    pdf_attachment_id: UUID | None = Field(
        default=None,
        foreign_key="attachments.id",
        nullable=True,
        ondelete="SET NULL",
    )


class InvoiceLine(Entity, table=True):
    __tablename__ = "invoice_lines"

    invoice_id: UUID = Field(
        foreign_key="invoices.id", nullable=False, index=True, ondelete="CASCADE"
    )
    product_id: UUID = Field(
        foreign_key="products.id", nullable=False, index=True, ondelete="RESTRICT"
    )
    description: str = Field(max_length=255, nullable=False)
    hsn_code: str = Field(default="", max_length=16, nullable=False)
    quantity: Decimal = Field(sa_type=Numeric(14, 3), nullable=False)
    unit_price: Decimal = Field(sa_type=Numeric(12, 2), nullable=False)
    gst_rate: Decimal = Field(default=Decimal("0"), sa_type=Numeric(5, 2), nullable=False)
    taxable_amount: Decimal = Field(sa_type=Numeric(12, 2), nullable=False)
    cgst_amount: Decimal = Field(default=Decimal("0"), sa_type=Numeric(12, 2), nullable=False)
    sgst_amount: Decimal = Field(default=Decimal("0"), sa_type=Numeric(12, 2), nullable=False)
    igst_amount: Decimal = Field(default=Decimal("0"), sa_type=Numeric(12, 2), nullable=False)


class Payment(Entity, table=True):
    __tablename__ = "payments"

    invoice_id: UUID = Field(
        foreign_key="invoices.id", nullable=False, index=True, ondelete="CASCADE"
    )
    amount: Decimal = Field(sa_type=Numeric(12, 2), nullable=False)
    method: str = Field(max_length=16, nullable=False)
    note: str | None = Field(default=None, sa_type=Text, nullable=True)
    attachment_id: UUID | None = Field(default=None, nullable=True)
    recorded_by_user_id: UUID | None = Field(
        default=None, foreign_key="users.id", nullable=True, ondelete="SET NULL"
    )
