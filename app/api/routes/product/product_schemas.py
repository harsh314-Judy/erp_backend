from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


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


class ComponentWrite(BaseModel):
    component_product_id: UUID | None = None
    component_raw_material_id: UUID | None = None
    quantity_per_unit: Decimal = Field(gt=0)

    @model_validator(mode="after")
    def one_component(self) -> "ComponentWrite":
        chosen = (self.component_product_id is None) + (self.component_raw_material_id is None)
        if chosen != 1:
            raise ValueError("Choose either a product or a raw material")
        return self


class ComponentRead(ComponentWrite):
    id: UUID
    position: int
    item_name: str | None = None


class RouteWrite(BaseModel):
    operation_ids: list[UUID]


class ProductCreate(BaseModel):
    product_name: str = Field(min_length=1, max_length=255)
    sku_number: str = Field(min_length=1, max_length=100)
    quantity: Decimal = Field(default=Decimal("0"), ge=0)
    gst: bool = False
    measurement_unit_id: UUID
    sale_price_without_gst: Decimal = Field(default=Decimal("0"), ge=0)
    description: str | None = None
    gst_percent: int = Field(default=0, ge=0, le=100)
    category_id: UUID
    alert_quantity: Decimal = Field(default=Decimal("0"), ge=0)
    quantity_per_bundle: int = Field(default=1, ge=1)
    product_type: str = "manufactured"
    hsn_code: str = ""
    responsible_user_id: UUID | None = None


class ProductUpdate(BaseModel):
    product_name: str | None = Field(default=None, min_length=1, max_length=255)
    sku_number: str | None = Field(default=None, min_length=1, max_length=100)
    quantity: Decimal | None = Field(default=None, ge=0)
    gst: bool | None = None
    measurement_unit_id: UUID | None = None
    sale_price_without_gst: Decimal | None = Field(default=None, ge=0)
    description: str | None = None
    gst_percent: int | None = Field(default=None, ge=0, le=100)
    category_id: UUID | None = None
    alert_quantity: Decimal | None = Field(default=None, ge=0)
    quantity_per_bundle: int | None = Field(default=None, ge=1)
    product_type: str | None = None
    hsn_code: str | None = None
    responsible_user_id: UUID | None = None


class ProductRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    product_name: str
    sku_number: str
    quantity: Decimal
    gst: bool
    measurement_unit_id: UUID
    sale_price_without_gst: Decimal | None = None
    description: str | None
    gst_percent: int
    category_id: UUID
    alert_quantity: Decimal
    quantity_per_bundle: int
    product_type: str = "manufactured"
    hsn_code: str = ""
    responsible_user_id: UUID | None = None
    on_hand: Decimal | None = None
    held: Decimal | None = None
    available: Decimal | None = None
    stock_status: str | None = None


class ProductOption(BaseModel):
    id: UUID
    product_name: str
    sku_number: str
    product_type: str
