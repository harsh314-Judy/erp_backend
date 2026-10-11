from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.api.routes.sales.sales_model import SalesProgress


class SaleCreate(BaseModel):
    customer_id: UUID
    product_id: UUID
    product_quantity: int = Field(ge=1)
    product_gst_override_percentage: int | None = Field(default=None, ge=0, le=100)
    is_gst: bool = False
    bundles: int = Field(default=0, ge=0)
    progress: SalesProgress = SalesProgress.ON_HOLD
    note: str | None = None


class SaleUpdate(BaseModel):
    customer_id: UUID | None = None
    product_id: UUID | None = None
    product_quantity: int | None = Field(default=None, ge=1)
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
    product_quantity: int
    product_gst_override_percentage: int | None
    is_gst: bool
    bundles: int
    progress: SalesProgress
    note: str | None
