from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class CustomerCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    is_company: bool = False
    gst_number: str | None = Field(default=None, max_length=20)
    address: str = Field(min_length=1)
    phone_number: str = Field(min_length=1, max_length=20)
    alt_phone_number: str | None = Field(default=None, max_length=20)
    email: str = Field(min_length=3, max_length=255)
    whatsapp_number: str | None = Field(default=None, max_length=20)
    is_whatsapp_different: bool = False


class CustomerUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    is_company: bool | None = None
    gst_number: str | None = Field(default=None, max_length=20)
    address: str | None = Field(default=None, min_length=1)
    phone_number: str | None = Field(default=None, min_length=1, max_length=20)
    alt_phone_number: str | None = Field(default=None, max_length=20)
    email: str | None = Field(default=None, min_length=3, max_length=255)
    whatsapp_number: str | None = Field(default=None, max_length=20)
    is_whatsapp_different: bool | None = None


class CustomerRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    is_company: bool
    gst_number: str | None
    address: str
    phone_number: str
    alt_phone_number: str | None
    email: str
    whatsapp_number: str | None
    is_whatsapp_different: bool
