from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class CompanyRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    company_name: str
    gstin: str
    state: str
    address: str
    delivery_charge: Decimal
    invoice_prefix: str


class CompanyUpdate(BaseModel):
    company_name: str = Field(min_length=1, max_length=255)
    gstin: str = ""
    state: str = ""
    address: str = ""
    delivery_charge: Decimal = Field(ge=0)
    invoice_prefix: str = Field(min_length=1, max_length=16)
