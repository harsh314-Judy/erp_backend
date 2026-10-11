from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class InviteCreate(BaseModel):
    email: str = Field(min_length=3, max_length=255)
    role_id: UUID


class InviteRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    email: str
    role_id: UUID
    token: str
    expiry_date: datetime
    invited_by_user_id: UUID | None
    accepted_at: datetime | None


class SignupRequest(BaseModel):
    token: str = Field(min_length=1, max_length=512)
    first_name: str = Field(min_length=1, max_length=150)
    last_name: str | None = Field(default=None, max_length=150)
    password: str = Field(min_length=8, max_length=128)


class LoginRequest(BaseModel):
    email: str = Field(min_length=3, max_length=255)
    password: str = Field(min_length=1, max_length=128)


class RefreshRequest(BaseModel):
    refresh_token: str = Field(min_length=1, max_length=512)


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class ForgotPasswordRequest(BaseModel):
    email: str = Field(min_length=3, max_length=255)


class ForgotPasswordResponse(BaseModel):
    message: str
    token: str | None = None


class ResetPasswordRequest(BaseModel):
    token: str = Field(min_length=1, max_length=512)
    password: str = Field(min_length=8, max_length=128)
