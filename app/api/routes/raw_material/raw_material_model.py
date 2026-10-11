from uuid import UUID

from sqlmodel import Field

from app.db.base import Entity


class RawMaterial(Entity, table=True):
    __tablename__ = "raw_materials"

    name: str = Field(max_length=255, nullable=False, index=True)
    quantity: int = Field(default=0, nullable=False)
    alert_quantity: int = Field(default=0, nullable=False)
    measurement_unit_id: UUID = Field(
        foreign_key="measurement_units.id",
        nullable=False,
        index=True,
        ondelete="RESTRICT",
    )
    price: int = Field(nullable=False)
