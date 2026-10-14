from datetime import datetime
from decimal import Decimal
from enum import Enum
from uuid import UUID

from sqlalchemy import DateTime, Enum as SqlEnum, Numeric, Text
from sqlmodel import Field

from app.db.base import Entity


class SalesProgress(str, Enum):
    ON_HOLD = "on hold"
    IN_PROGRESS = "in progress"
    DELIVERED = "delivered"
    COMPLETED = "completed"


class Sale(Entity, table=True):
    __tablename__ = "sales"

    customer_id: UUID = Field(
        foreign_key="customers.id",
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
    product_quantity: Decimal = Field(sa_type=Numeric(14, 3), nullable=False)
    product_gst_override_percentage: int | None = Field(default=None, nullable=True)
    is_gst: bool = Field(default=False, nullable=False)
    bundles: int = Field(default=0, nullable=False)
    progress: SalesProgress = Field(
        default=SalesProgress.ON_HOLD,
        sa_type=SqlEnum(
            SalesProgress,
            name="sales_progress",
            native_enum=True,
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
        ),
        nullable=False,
    )
    note: str | None = Field(default=None, sa_type=Text, nullable=True)


class SalesOrder(Entity, table=True):
    __tablename__ = "sales_orders"

    customer_id: UUID = Field(
        foreign_key="customers.id", nullable=False, index=True, ondelete="RESTRICT"
    )
    notes: str | None = Field(default=None, sa_type=Text, nullable=True)
    status: str = Field(default="open", max_length=32, nullable=False, index=True)
    packaging_user_id: UUID | None = Field(
        default=None, foreign_key="users.id", nullable=True, index=True, ondelete="SET NULL"
    )
    created_by_user_id: UUID | None = Field(
        default=None, foreign_key="users.id", nullable=True, ondelete="SET NULL"
    )
    delivery_charge: Decimal = Field(default=Decimal("0"), sa_type=Numeric(12, 2), nullable=False)


class SalesOrderLine(Entity, table=True):
    __tablename__ = "sales_order_lines"

    sales_order_id: UUID = Field(
        foreign_key="sales_orders.id", nullable=False, index=True, ondelete="CASCADE"
    )
    product_id: UUID = Field(
        foreign_key="products.id", nullable=False, index=True, ondelete="RESTRICT"
    )
    quantity: Decimal = Field(sa_type=Numeric(14, 3), nullable=False)
    held_quantity: Decimal = Field(default=Decimal("0"), sa_type=Numeric(14, 3), nullable=False)
    unit_price: Decimal = Field(sa_type=Numeric(12, 2), nullable=False)
    shortfall_choice: str | None = Field(default=None, max_length=16, nullable=True)
    reservation_id: UUID | None = Field(default=None, nullable=True)
