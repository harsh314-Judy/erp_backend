from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.api.routes.sales.sales_model import SalesProgress


class SaleCreate(BaseModel):
    customer_id: UUID
    product_id: UUID
    product_quantity: Decimal = Field(gt=0)
    product_gst_override_percentage: int | None = Field(default=None, ge=0, le=100)
    is_gst: bool = False
    bundles: int = Field(default=0, ge=0)
    progress: SalesProgress = SalesProgress.ON_HOLD
    note: str | None = None


class SaleUpdate(BaseModel):
    customer_id: UUID | None = None
    product_id: UUID | None = None
    product_quantity: Decimal | None = Field(default=None, gt=0)
    product_gst_override_percentage: int | None = Field(default=None, ge=0, le=100)
    is_gst: bool | None = None
    bundles: int | None = Field(default=None, ge=0)
    progress: SalesProgress | None = None
    note: str | None = None


class SaleRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    customer_id: UUID
    product_id: UUID
    product_quantity: Decimal
    product_gst_override_percentage: int | None
    is_gst: bool
    bundles: int
    progress: SalesProgress
    note: str | None


class SalesOrderLineWrite(BaseModel):
    product_id: UUID
    quantity: Decimal = Field(gt=0)
    shortfall_choice: str | None = None
    source_purchase_order_id: UUID | None = None


class SalesOrderCreate(BaseModel):
    customer_id: UUID
    notes: str | None = None
    packaging_user_id: UUID | None = None
    dispatch_by: datetime | None = None
    turnaround_days: int | None = Field(default=None, ge=1)
    gst_billing: bool = True
    lines: list[SalesOrderLineWrite] = Field(min_length=1)


class SalesOrderLineRead(BaseModel):
    id: UUID
    product_id: UUID
    product_name: str | None = None
    product_type: str | None = None
    quantity: Decimal
    held_quantity: Decimal
    unit_price: Decimal | None = None
    shortfall_choice: str | None = None
    source_purchase_order_id: UUID | None = None


class SalesOrderRead(BaseModel):
    id: UUID
    customer_id: UUID
    customer_name: str | None = None
    notes: str | None
    status: str
    packaging_user_id: UUID | None
    packaging_name: str | None = None
    delivery_charge: Decimal
    dispatch_by: datetime | None = None
    turnaround_days: int | None = None
    gst_billing: bool = True
    lines: list[SalesOrderLineRead]
    invoice_id: UUID | None = None
    invoice_has_pdf: bool = False
    updated_at: datetime | None = None


class SalesSource(BaseModel):
    line_id: UUID
    source_purchase_order_id: UUID


class SalesOrderStatusUpdate(BaseModel):
    status: str
    sources: list[SalesSource] = Field(default_factory=list)


class PackagingAssign(BaseModel):
    packaging_user_id: UUID
