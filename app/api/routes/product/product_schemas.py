from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


def _blank(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


class MeasurementUnitCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    abbreviation: str | None = Field(default=None, max_length=16)
    detail: str | None = Field(default=None, max_length=80)

    @field_validator("abbreviation", "detail", mode="before")
    @classmethod
    def empty_is_missing(cls, value: object) -> str | None:
        return _blank(value)


class MeasurementUnitUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    abbreviation: str | None = Field(default=None, max_length=16)
    detail: str | None = Field(default=None, max_length=80)

    @field_validator("abbreviation", "detail", mode="before")
    @classmethod
    def empty_is_missing(cls, value: object) -> str | None:
        return _blank(value)


class MeasurementUnitRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    abbreviation: str | None = None
    detail: str | None = None
    expires_at: datetime | None = None


class ReplaceRequest(BaseModel):
    replacement_id: UUID | None = None
    temporary_name: str | None = Field(default=None, min_length=1, max_length=150)
    detail: str | None = Field(default=None, max_length=80)

    @model_validator(mode="after")
    def one_choice(self):
        has_existing = self.replacement_id is not None
        has_temporary = bool(self.temporary_name and self.temporary_name.strip())
        if has_existing == has_temporary:
            raise ValueError("Choose an existing item or a temporary name")
        return self


class ProductCategoryCreate(BaseModel):
    name: str = Field(min_length=1, max_length=150)


class ProductCategoryUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=150)


class ProductCategoryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    expires_at: datetime | None = None


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


class RouteStepWrite(BaseModel):
    operation_id: UUID
    allows_send_out: bool = False
    standard_scrap_percent: Decimal | None = Field(default=None, ge=0, le=100)


class RouteStepRead(BaseModel):
    operation_id: UUID
    allows_send_out: bool = False
    standard_scrap_percent: Decimal | None = None


class RouteWrite(BaseModel):
    operation_ids: list[UUID] = Field(default_factory=list)
    steps: list[RouteStepWrite] | None = None


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
    weight_per_piece: Decimal | None = Field(default=None, ge=0)
    make_days: int = Field(default=7, ge=0)
    buy_days: int = Field(default=7, ge=0)
    ship_days: int = Field(default=2, ge=0)
    buffer_days: int = Field(default=2, ge=0)
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
    weight_per_piece: Decimal | None = Field(default=None, ge=0)
    make_days: int | None = Field(default=None, ge=0)
    buy_days: int | None = Field(default=None, ge=0)
    ship_days: int | None = Field(default=None, ge=0)
    buffer_days: int | None = Field(default=None, ge=0)
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
    weight_per_piece: Decimal | None = None
    make_days: int = 7
    buy_days: int = 7
    ship_days: int = 2
    buffer_days: int = 2
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
