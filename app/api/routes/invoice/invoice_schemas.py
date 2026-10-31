from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class InvoiceLinePrice(BaseModel):
    line_id: UUID
    mrp: Decimal = Field(ge=0)
    gst_percent: Decimal = Field(ge=0, le=100)


class InvoiceIssue(BaseModel):
    lines: list[InvoiceLinePrice] = Field(min_length=1)


class InvoiceDraftLine(BaseModel):
    line_id: UUID
    product_name: str
    quantity: Decimal
    unit: str
    mrp: Decimal
    catalog_price: Decimal
    gst_percent: Decimal


class InvoiceDraft(BaseModel):
    customer_name: str
    customer_address: str
    customer_state: str
    customer_gst_number: str | None
    customer_phone: str
    delivery_charge: Decimal
    same_state: bool
    seller_name: str
    seller_gstin: str
    lines: list[InvoiceDraftLine]
    has_pdf: bool
    invoice_id: UUID | None = None
    invoice_number: str | None = None


class InvoiceLineRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    product_id: UUID
    description: str
    hsn_code: str
    quantity: Decimal
    unit_price: Decimal
    gst_rate: Decimal
    taxable_amount: Decimal
    cgst_amount: Decimal
    sgst_amount: Decimal
    igst_amount: Decimal


class PaymentCreate(BaseModel):
    amount: Decimal = Field(gt=0)
    method: str
    note: str | None = None
    attachment_id: UUID | None = None


class PaymentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    amount: Decimal
    method: str
    note: str | None
    attachment_id: UUID | None
    created_at: datetime


class InvoiceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    sales_order_id: UUID
    customer_id: UUID
    number: str
    status: str
    same_state: bool
    taxable_amount: Decimal
    cgst_amount: Decimal
    sgst_amount: Decimal
    igst_amount: Decimal
    delivery_charge: Decimal
    total_amount: Decimal
    amount_paid: Decimal
    lines: list[InvoiceLineRead] = []
    payments: list[PaymentRead] = []
    has_pdf: bool = False
