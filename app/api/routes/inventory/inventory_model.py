from decimal import Decimal
from uuid import UUID

from sqlalchemy import Numeric, Text
from sqlmodel import Field

from app.db.base import Entity


class InventoryMovement(Entity, table=True):
    __tablename__ = "inventory_movements"

    product_id: UUID | None = Field(
        default=None, foreign_key="products.id", nullable=True, index=True, ondelete="RESTRICT"
    )
    raw_material_id: UUID | None = Field(
        default=None,
        foreign_key="raw_materials.id",
        nullable=True,
        index=True,
        ondelete="RESTRICT",
    )
    quantity: Decimal = Field(sa_type=Numeric(14, 3), nullable=False)
    reason: str = Field(max_length=32, nullable=False, index=True)
    source_type: str = Field(max_length=32, nullable=False)
    source_id: UUID | None = Field(default=None, nullable=True, index=True)
    user_id: UUID | None = Field(
        default=None, foreign_key="users.id", nullable=True, index=True, ondelete="SET NULL"
    )
    note: str | None = Field(default=None, sa_type=Text, nullable=True)


class StockReservation(Entity, table=True):
    __tablename__ = "stock_reservations"

    product_id: UUID | None = Field(
        default=None, foreign_key="products.id", nullable=True, index=True, ondelete="RESTRICT"
    )
    raw_material_id: UUID | None = Field(
        default=None,
        foreign_key="raw_materials.id",
        nullable=True,
        index=True,
        ondelete="RESTRICT",
    )
    quantity: Decimal = Field(sa_type=Numeric(14, 3), nullable=False)
    status: str = Field(default="held", max_length=16, nullable=False, index=True)
    source_type: str = Field(max_length=32, nullable=False)
    source_id: UUID = Field(nullable=False, index=True)


class StockRequest(Entity, table=True):
    __tablename__ = "stock_requests"

    product_id: UUID | None = Field(
        default=None, foreign_key="products.id", nullable=True, index=True, ondelete="RESTRICT"
    )
    raw_material_id: UUID | None = Field(
        default=None,
        foreign_key="raw_materials.id",
        nullable=True,
        index=True,
        ondelete="RESTRICT",
    )
    quantity: Decimal = Field(sa_type=Numeric(14, 3), nullable=False)
    note: str | None = Field(default=None, sa_type=Text, nullable=True)
    status: str = Field(default="open", max_length=16, nullable=False, index=True)
    requested_by_user_id: UUID | None = Field(
        default=None, foreign_key="users.id", nullable=True, ondelete="SET NULL"
    )
    responsible_user_id: UUID | None = Field(
        default=None, foreign_key="users.id", nullable=True, index=True, ondelete="SET NULL"
    )
