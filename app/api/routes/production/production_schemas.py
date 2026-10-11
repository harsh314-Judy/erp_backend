from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ProductionJobCreate(BaseModel):
    product_id: UUID
    current_operation_id: UUID
    notes: str | None = None
    raw_material_used: dict = Field(default_factory=dict)
    operation_flow: dict = Field(default_factory=dict)
    product_used: dict = Field(default_factory=dict)
    quantity: int = Field(default=0, ge=0)
    raw_material_used_after_production: dict = Field(default_factory=dict)
    product_used_after_production: dict = Field(default_factory=dict)


class ProductionJobUpdate(BaseModel):
    product_id: UUID | None = None
    current_operation_id: UUID | None = None
    notes: str | None = None
    raw_material_used: dict | None = None
    operation_flow: dict | None = None
    product_used: dict | None = None
    quantity: int | None = Field(default=None, ge=0)
    raw_material_used_after_production: dict | None = None
    product_used_after_production: dict | None = None


class ProductionJobRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    product_id: UUID
    current_operation_id: UUID
    notes: str | None
    raw_material_used: dict
    operation_flow: dict
    product_used: dict
    quantity: int
    raw_material_used_after_production: dict
    product_used_after_production: dict
