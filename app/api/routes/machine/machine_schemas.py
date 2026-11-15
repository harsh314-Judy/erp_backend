from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class MachineCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    operation_id: UUID
    note: str | None = None


class MachineUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    status: str | None = Field(default=None, pattern="^(up|down)$")
    note: str | None = None


class MachineRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    operation_id: UUID
    operation_name: str = ""
    status: str
    note: str | None = None
