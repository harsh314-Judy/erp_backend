from sqlalchemy import Text
from sqlmodel import Field

from app.db.base import Entity


class Customer(Entity, table=True):
    __tablename__ = "customers"

    name: str = Field(max_length=255, nullable=False, index=True)
    is_company: bool = Field(default=False, nullable=False)
    gst_number: str | None = Field(default=None, max_length=20, nullable=True)
    address: str = Field(sa_type=Text, nullable=False)
    state: str = Field(default="", max_length=80, nullable=False)
    whatsapp_mode: str = Field(default="main", max_length=20, nullable=False)
    phone_number: str = Field(max_length=20, nullable=False)
    alt_phone_number: str | None = Field(default=None, max_length=20, nullable=True)
    email: str = Field(max_length=255, nullable=False, index=True)
    whatsapp_number: str | None = Field(default=None, max_length=20, nullable=True)
    is_whatsapp_different: bool = Field(default=False, nullable=False)
