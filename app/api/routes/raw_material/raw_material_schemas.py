from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class RawMaterialCategoryCreate(BaseModel):
    name: str = Field(min_length=1, max_length=150)


class RawMaterialCategoryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str


class RawMaterialCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    quantity: Decimal = Field(default=Decimal("0"), ge=0)
    alert_quantity: Decimal = Field(default=Decimal("0"), ge=0)
    measurement_unit_id: UUID
    price: Decimal = Field(default=Decimal("0"), ge=0)
    purchase_price: Decimal = Field(default=Decimal("0"), ge=0)
    description: str | None = None
    kind: str = "sheet"
    responsible_user_id: UUID | None = None
    category_id: UUID
    supplier_id: UUID | None = None


class RawMaterialUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    quantity: Decimal | None = Field(default=None, ge=0)
    alert_quantity: Decimal | None = Field(default=None, ge=0)
    measurement_unit_id: UUID | None = None
    price: Decimal | None = Field(default=None, ge=0)
    purchase_price: Decimal | None = Field(default=None, ge=0)
    description: str | None = None
    kind: str | None = None
    responsible_user_id: UUID | None = None
    category_id: UUID | None = None
    supplier_id: UUID | None = None


class RawMaterialRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    quantity: Decimal
    alert_quantity: Decimal
    measurement_unit_id: UUID
    price: Decimal | None = None
    purchase_price: Decimal | None = None
    description: str | None = None
    kind: str = "sheet"
    responsible_user_id: UUID | None = None
    category_id: UUID | None = None
    supplier_id: UUID | None = None
    on_hand: Decimal | None = None
    held: Decimal | None = None
    available: Decimal | None = None
    stock_status: str | None = None


class RawMaterialOption(BaseModel):
    id: UUID
    name: str
    kind: str
