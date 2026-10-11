from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class RawMaterialCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    quantity: int = Field(default=0, ge=0)
    alert_quantity: int = Field(default=0, ge=0)
    measurement_unit_id: UUID
    price: int = Field(ge=0)


class RawMaterialUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    quantity: int | None = Field(default=None, ge=0)
    alert_quantity: int | None = Field(default=None, ge=0)
    measurement_unit_id: UUID | None = None
    price: int | None = Field(default=None, ge=0)


class RawMaterialRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    quantity: int
    alert_quantity: int
    measurement_unit_id: UUID
    price: int
