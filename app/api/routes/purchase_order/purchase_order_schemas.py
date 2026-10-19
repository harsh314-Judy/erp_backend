from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class PurchaseOrderRawMaterialCreate(BaseModel):
    raw_material_id: UUID
    supplier_id: UUID
    quantity: Decimal = Field(ge=1)
    per_unit_price: Decimal = Field(ge=0)
    note: str | None = None
    status: bool = False


class PurchaseOrderRawMaterialUpdate(BaseModel):
    raw_material_id: UUID | None = None
    supplier_id: UUID | None = None
    quantity: Decimal | None = Field(default=None, ge=1)
    per_unit_price: Decimal | None = Field(default=None, ge=0)
    note: str | None = None
    status: bool | None = None


class PurchaseOrderRawMaterialRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    raw_material_id: UUID
    supplier_id: UUID
    quantity: Decimal
    per_unit_price: Decimal
    note: str | None
    status: bool


class PurchaseOrderProductCreate(BaseModel):
    supplier_id: UUID
    product_id: UUID
    quantity: Decimal = Field(ge=1)
    per_unit_price: Decimal = Field(ge=0)
    note: str | None = None
    status: bool = False


class PurchaseOrderProductUpdate(BaseModel):
    supplier_id: UUID | None = None
    product_id: UUID | None = None
    quantity: Decimal | None = Field(default=None, ge=1)
    per_unit_price: Decimal | None = Field(default=None, ge=0)
    note: str | None = None
    status: bool | None = None


class PurchaseOrderLineWrite(BaseModel):
    product_id: UUID | None = None
    raw_material_id: UUID | None = None
    quantity: Decimal = Field(gt=0)
    unit_price: Decimal = Field(ge=0)


class PurchaseOrderUpdate(BaseModel):
    status: str | None = None
    notes: str | None = None
    expected_vehicle_plate: str | None = None
    supplier_id: UUID | None = None
    lines: list[PurchaseOrderLineWrite] | None = None


class PurchaseOrderProductRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    supplier_id: UUID
    product_id: UUID
    quantity: Decimal
    per_unit_price: Decimal
    note: str | None
    status: bool
