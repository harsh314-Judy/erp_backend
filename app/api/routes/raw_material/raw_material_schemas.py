from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


class RawMaterialCategoryCreate(BaseModel):
    name: str = Field(min_length=1, max_length=150)


class RawMaterialCategoryUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=150)


class RawMaterialCategoryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    expires_at: datetime | None = None


class ReplaceRequest(BaseModel):
    replacement_id: UUID | None = None
    temporary_name: str | None = Field(default=None, min_length=1, max_length=150)

    @model_validator(mode="after")
    def one_choice(self):
        has_existing = self.replacement_id is not None
        has_temporary = bool(self.temporary_name and self.temporary_name.strip())
        if has_existing == has_temporary:
            raise ValueError("Choose an existing item or a temporary name")
        return self


class RawMaterialCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    quantity: Decimal = Field(default=Decimal("0"), ge=0)
    alert_quantity: Decimal = Field(default=Decimal("0"), ge=0)
    measurement_unit_id: UUID
    price: Decimal = Field(default=Decimal("0"), ge=0)
    purchase_price: Decimal = Field(default=Decimal("0"), ge=0)
    description: str | None = None
    kind: str = "sheet"
    stock_group: str = "core"
    responsible_user_id: UUID | None = None
    category_id: UUID
    supplier_id: UUID | None = None
    thickness: str | None = Field(default=None, max_length=32)
    grade: str | None = Field(default=None, max_length=32)
    size: str | None = Field(default=None, max_length=64)


class RawMaterialUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    quantity: Decimal | None = Field(default=None, ge=0)
    alert_quantity: Decimal | None = Field(default=None, ge=0)
    measurement_unit_id: UUID | None = None
    price: Decimal | None = Field(default=None, ge=0)
    purchase_price: Decimal | None = Field(default=None, ge=0)
    description: str | None = None
    kind: str | None = None
    stock_group: str | None = None
    responsible_user_id: UUID | None = None
    category_id: UUID | None = None
    supplier_id: UUID | None = None
    thickness: str | None = Field(default=None, max_length=32)
    grade: str | None = Field(default=None, max_length=32)
    size: str | None = Field(default=None, max_length=64)


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
    stock_group: str = "core"
    responsible_user_id: UUID | None = None
    category_id: UUID | None = None
    supplier_id: UUID | None = None
    thickness: str | None = None
    grade: str | None = None
    size: str | None = None
    parent_raw_material_id: UUID | None = None
    is_remnant: bool = False
    on_hand: Decimal | None = None
    held: Decimal | None = None
    available: Decimal | None = None
    stock_status: str | None = None


class RawMaterialOption(BaseModel):
    id: UUID
    name: str
    kind: str
    stock_group: str = "core"
