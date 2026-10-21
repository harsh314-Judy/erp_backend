from uuid import UUID

from pydantic import BaseModel, Field


class InviteCreate(BaseModel):
    email: str = Field(min_length=3, max_length=255)
    first_name: str = Field(min_length=1, max_length=150)
    last_name: str | None = Field(default=None, max_length=150)
    role_id: UUID


class SignupRequest(BaseModel):
    token: str = Field(min_length=1, max_length=512)
    password: str = Field(min_length=8, max_length=128)


class LoginRequest(BaseModel):
    email: str = Field(min_length=3, max_length=255)
    password: str = Field(min_length=1, max_length=128)
    device_model: str | None = Field(default=None, max_length=80)
    device_platform: str | None = Field(default=None, max_length=48)
    device_mobile: bool | None = None


class ForgotPasswordRequest(BaseModel):
    email: str = Field(min_length=3, max_length=255)


class ResetPasswordRequest(BaseModel):
    token: str = Field(min_length=1, max_length=512)
    password: str = Field(min_length=8, max_length=128)
