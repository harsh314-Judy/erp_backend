from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class OperationCreate(BaseModel):
    name: str = Field(min_length=1, max_length=150)
    description: str | None = None


class OperationUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=150)
    description: str | None = None


class OperationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    description: str | None


class UserOperationCreate(BaseModel):
    operation_id: UUID
    user_id: UUID


class UserOperationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    operation_id: UUID
    user_id: UUID
