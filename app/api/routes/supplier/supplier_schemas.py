from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class SupplierCreate(BaseModel):
    supplier_company_name: str = Field(min_length=1, max_length=255)
    contact_person_name: str = Field(min_length=1, max_length=150)
    phone: str = Field(min_length=1, max_length=20)
    email: str = Field(min_length=3, max_length=255)
    is_gst: bool = False
    gst_number: str | None = Field(default=None, max_length=20)
    address: str = Field(min_length=1)
    alt_number: str | None = Field(default=None, max_length=20)
    supply_kind: str = "both"
    raw_material_ids: list[UUID] = []
    product_ids: list[UUID] = []


class SupplierUpdate(BaseModel):
    supplier_company_name: str | None = Field(default=None, min_length=1, max_length=255)
    contact_person_name: str | None = Field(default=None, min_length=1, max_length=150)
    phone: str | None = Field(default=None, min_length=1, max_length=20)
    email: str | None = Field(default=None, min_length=3, max_length=255)
    is_gst: bool | None = None
    gst_number: str | None = Field(default=None, max_length=20)
    address: str | None = Field(default=None, min_length=1)
    alt_number: str | None = Field(default=None, max_length=20)
    supply_kind: str | None = None
    raw_material_ids: list[UUID] | None = None
    product_ids: list[UUID] | None = None


class SupplierRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    supplier_company_name: str
    contact_person_name: str
    phone: str
    email: str
    is_gst: bool
    gst_number: str | None
    address: str
    alt_number: str | None
    supply_kind: str = "both"
    raw_material_ids: list[UUID] = []
    product_ids: list[UUID] = []


class RawMaterialSupplierCreate(BaseModel):
    raw_material_id: UUID
    supplier_id: UUID
    current_count: int = Field(default=0, ge=0)


class RawMaterialSupplierUpdate(BaseModel):
    current_count: int | None = Field(default=None, ge=0)


class RawMaterialSupplierRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    raw_material_id: UUID
    supplier_id: UUID
    current_count: int


class ProductSupplierCreate(BaseModel):
    product_id: UUID
    supplier_id: UUID
    current_count: int = Field(default=0, ge=0)


class ProductSupplierUpdate(BaseModel):
    current_count: int | None = Field(default=None, ge=0)


class ProductSupplierRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    product_id: UUID
    supplier_id: UUID
    current_count: int
