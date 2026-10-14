from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field


class AdjustmentCreate(BaseModel):
    product_id: UUID | None = None
    raw_material_id: UUID | None = None
    quantity_delta: Decimal
    reason: str = Field(min_length=3)


class StockRequestCreate(BaseModel):
    product_id: UUID | None = None
    raw_material_id: UUID | None = None
    quantity: Decimal = Field(gt=0)
    note: str | None = None
