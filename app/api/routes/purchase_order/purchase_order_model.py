from decimal import Decimal
from uuid import UUID

from sqlalchemy import Numeric, Text
from sqlmodel import Field

from app.db.base import Entity


class PurchaseOrderRawMaterial(Entity, table=True):
    __tablename__ = "purchase_order_raw_materials"

    raw_material_id: UUID = Field(
        foreign_key="raw_materials.id",
        nullable=False,
        index=True,
        ondelete="RESTRICT",
    )
    supplier_id: UUID = Field(
        foreign_key="suppliers.id",
        nullable=False,
        index=True,
        ondelete="RESTRICT",
    )
    quantity: Decimal = Field(sa_type=Numeric(14, 3), nullable=False)
    per_unit_price: Decimal = Field(sa_type=Numeric(12, 2), nullable=False)
    note: str | None = Field(default=None, sa_type=Text, nullable=True)
    status: bool = Field(default=False, nullable=False)


class PurchaseOrderProduct(Entity, table=True):
    __tablename__ = "purchase_order_products"

    supplier_id: UUID = Field(
        foreign_key="suppliers.id",
        nullable=False,
        index=True,
        ondelete="RESTRICT",
    )
    product_id: UUID = Field(
        foreign_key="products.id",
        nullable=False,
        index=True,
        ondelete="RESTRICT",
    )
    quantity: Decimal = Field(sa_type=Numeric(14, 3), nullable=False)
    per_unit_price: Decimal = Field(sa_type=Numeric(12, 2), nullable=False)
    note: str | None = Field(default=None, sa_type=Text, nullable=True)
    status: bool = Field(default=False, nullable=False)


class PurchaseOrder(Entity, table=True):
    __tablename__ = "purchase_orders"

    supplier_id: UUID = Field(
        foreign_key="suppliers.id", nullable=False, index=True, ondelete="RESTRICT"
    )
    notes: str | None = Field(default=None, sa_type=Text, nullable=True)
    status: str = Field(default="draft", max_length=32, nullable=False, index=True)
    expected_vehicle_plate: str | None = Field(default=None, max_length=20, nullable=True)
    arrived_vehicle_plate: str | None = Field(default=None, max_length=20, nullable=True)
    plate_mismatch_note: str | None = Field(default=None, sa_type=Text, nullable=True)
    receipt_attachment_id: UUID | None = Field(default=None, nullable=True)
    created_by_user_id: UUID | None = Field(
        default=None, foreign_key="users.id", nullable=True, ondelete="SET NULL"
    )
    stock_received: bool = Field(default=False, nullable=False)


class PurchaseOrderLine(Entity, table=True):
    __tablename__ = "purchase_order_lines"

    purchase_order_id: UUID = Field(
        foreign_key="purchase_orders.id", nullable=False, index=True, ondelete="CASCADE"
    )
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
    unit_price: Decimal = Field(sa_type=Numeric(12, 2), nullable=False)


class PurchaseRequest(Entity, table=True):
    __tablename__ = "purchase_requests"

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
    source: str = Field(max_length=32, nullable=False)
    source_id: UUID | None = Field(default=None, nullable=True, index=True)
    status: str = Field(default="open", max_length=32, nullable=False, index=True)
    purchase_order_id: UUID | None = Field(
        default=None,
        foreign_key="purchase_orders.id",
        nullable=True,
        index=True,
        ondelete="SET NULL",
    )
