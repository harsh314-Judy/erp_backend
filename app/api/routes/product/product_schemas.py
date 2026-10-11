from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class MeasurementUnitCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)


class MeasurementUnitUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)


class MeasurementUnitRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str


class ProductCategoryCreate(BaseModel):
    name: str = Field(min_length=1, max_length=150)


class ProductCategoryUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=150)


class ProductCategoryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str


class ProductCreate(BaseModel):
    product_name: str = Field(min_length=1, max_length=255)
    sku_number: str = Field(min_length=1, max_length=100)
    quantity: int = Field(default=0, ge=0)
    gst: bool = False
    measurement_unit_id: UUID
    sale_price_without_gst: int = Field(ge=0)
    description: str | None = None
    gst_percent: int = Field(default=0, ge=0, le=100)
    category_id: UUID
    alert_quantity: int = Field(default=0, ge=0)
    quantity_per_bundle: int = Field(default=1, ge=1)


class ProductUpdate(BaseModel):
    product_name: str | None = Field(default=None, min_length=1, max_length=255)
    sku_number: str | None = Field(default=None, min_length=1, max_length=100)
    quantity: int | None = Field(default=None, ge=0)
    gst: bool | None = None
    measurement_unit_id: UUID | None = None
    sale_price_without_gst: int | None = Field(default=None, ge=0)
    description: str | None = None
    gst_percent: int | None = Field(default=None, ge=0, le=100)
    category_id: UUID | None = None
    alert_quantity: int | None = Field(default=None, ge=0)
    quantity_per_bundle: int | None = Field(default=None, ge=1)


class ProductRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    product_name: str
    sku_number: str
    quantity: int
    gst: bool
    measurement_unit_id: UUID
    sale_price_without_gst: int
    description: str | None
    gst_percent: int
    category_id: UUID
    alert_quantity: int
    quantity_per_bundle: int
