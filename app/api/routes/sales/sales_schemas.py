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


class SalesOrderCreate(BaseModel):
    customer_id: UUID
    notes: str | None = None
    packaging_user_id: UUID | None = None
    lines: list[SalesOrderLineWrite] = Field(min_length=1)


class SalesOrderLineRead(BaseModel):
    id: UUID
    product_id: UUID
    product_name: str | None = None
    quantity: Decimal
    held_quantity: Decimal
    unit_price: Decimal | None = None
    shortfall_choice: str | None = None


class SalesOrderRead(BaseModel):
    id: UUID
    customer_id: UUID
    customer_name: str | None = None
    notes: str | None
    status: str
    packaging_user_id: UUID | None
    packaging_name: str | None = None
    delivery_charge: Decimal
    lines: list[SalesOrderLineRead]
    invoice_id: UUID | None = None
    invoice_has_pdf: bool = False
    updated_at: datetime | None = None


class SalesOrderStatusUpdate(BaseModel):
    status: str


class PackagingAssign(BaseModel):
    packaging_user_id: UUID
