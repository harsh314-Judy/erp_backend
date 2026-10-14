from decimal import Decimal
from uuid import UUID

from sqlalchemy import Numeric, Text
from sqlmodel import Field

from app.db.base import Entity


class RawMaterial(Entity, table=True):
    __tablename__ = "raw_materials"

    name: str = Field(max_length=255, nullable=False, index=True)
    quantity: Decimal = Field(default=Decimal("0"), sa_type=Numeric(14, 3), nullable=False)
    alert_quantity: Decimal = Field(default=Decimal("0"), sa_type=Numeric(14, 3), nullable=False)
    measurement_unit_id: UUID = Field(
        foreign_key="measurement_units.id",
        nullable=False,
        index=True,
        ondelete="RESTRICT",
    )
    price: Decimal = Field(default=Decimal("0"), sa_type=Numeric(12, 2), nullable=False)
    purchase_price: Decimal = Field(default=Decimal("0"), sa_type=Numeric(12, 2), nullable=False)
    description: str | None = Field(default=None, sa_type=Text, nullable=True)
    kind: str = Field(default="sheet", max_length=32, nullable=False)
    responsible_user_id: UUID | None = Field(
        default=None,
        foreign_key="users.id",
        nullable=True,
        index=True,
        ondelete="SET NULL",
    )
