from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class RoleCreate(BaseModel):
    role_name: str = Field(min_length=1, max_length=100)


class RoleUpdate(BaseModel):
    role_name: str | None = Field(default=None, min_length=1, max_length=100)


class RoleRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    role_name: str


class UserCreate(BaseModel):
    first_name: str = Field(min_length=1, max_length=150)
    last_name: str | None = Field(default=None, max_length=150)
    email: str = Field(min_length=3, max_length=255)
    password: str = Field(min_length=8, max_length=128)
    role_id: UUID


class UserUpdate(BaseModel):
    first_name: str | None = Field(default=None, min_length=1, max_length=150)
    last_name: str | None = Field(default=None, max_length=150)
    email: str | None = Field(default=None, min_length=3, max_length=255)
    password: str | None = Field(default=None, min_length=8, max_length=128)
    role_id: UUID | None = None


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    first_name: str
    last_name: str | None
    email: str
    role_id: UUID
    role_name: str | None = None


class PasswordChangeRequest(BaseModel):
    old_password: str = Field(min_length=1, max_length=128)
    new_password: str = Field(min_length=8, max_length=128)
