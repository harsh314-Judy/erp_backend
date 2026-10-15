from decimal import Decimal

from sqlalchemy import Numeric, Text
from sqlmodel import Field

from app.db.base import Entity


class CompanySettings(Entity, table=True):
    __tablename__ = "company_settings"

    company_name: str = Field(default="Sai Daya Steel", max_length=255, nullable=False)
    gstin: str = Field(default="", max_length=20, nullable=False)
    state: str = Field(default="", max_length=80, nullable=False)
    address: str = Field(default="", sa_type=Text, nullable=False)
    delivery_charge: Decimal = Field(default=Decimal("0"), sa_type=Numeric(12, 2), nullable=False)
    invoice_prefix: str = Field(default="INV", max_length=16, nullable=False)
