from decimal import Decimal
from uuid import UUID

from sqlalchemy import Numeric, Text
from sqlmodel import Field

from app.db.base import Entity


class MeasurementUnit(Entity, table=True):
    __tablename__ = "measurement_units"

    name: str = Field(max_length=100, unique=True, nullable=False, index=True)


class ProductCategory(Entity, table=True):
    __tablename__ = "product_categories"

    name: str = Field(max_length=150, unique=True, nullable=False, index=True)


class Product(Entity, table=True):
    __tablename__ = "products"

    product_name: str = Field(max_length=255, nullable=False, index=True)
    sku_number: str = Field(max_length=100, unique=True, nullable=False, index=True)
    quantity: Decimal = Field(default=Decimal("0"), sa_type=Numeric(14, 3), nullable=False)
    gst: bool = Field(default=False, nullable=False)
    product_type: str = Field(default="manufactured", max_length=20, nullable=False)
    hsn_code: str = Field(default="", max_length=16, nullable=False)
    responsible_user_id: UUID | None = Field(
        default=None,
        foreign_key="users.id",
        nullable=True,
        index=True,
        ondelete="SET NULL",
    )
    measurement_unit_id: UUID = Field(
        foreign_key="measurement_units.id",
        nullable=False,
        index=True,
        ondelete="RESTRICT",
    )
    sale_price_without_gst: Decimal = Field(
        default=Decimal("0"), sa_type=Numeric(12, 2), nullable=False
    )
    last_purchase_price: Decimal | None = Field(
        default=None, sa_type=Numeric(12, 2), nullable=True
    )
    description: str | None = Field(default=None, sa_type=Text, nullable=True)
    gst_percent: int = Field(default=0, nullable=False)
    category_id: UUID = Field(
        foreign_key="product_categories.id",
        nullable=False,
        index=True,
        ondelete="RESTRICT",
    )
    alert_quantity: Decimal = Field(default=Decimal("0"), sa_type=Numeric(14, 3), nullable=False)
    quantity_per_bundle: int = Field(default=1, nullable=False)


class ProductRouteStep(Entity, table=True):
    __tablename__ = "product_route_steps"

    product_id: UUID = Field(
        foreign_key="products.id", nullable=False, index=True, ondelete="CASCADE"
    )
    operation_id: UUID = Field(
        foreign_key="operations.id", nullable=False, index=True, ondelete="RESTRICT"
    )
    position: int = Field(nullable=False)


class ProductComponent(Entity, table=True):
    """One input needed to make a single unit of a product."""

    __tablename__ = "product_components"

    product_id: UUID = Field(
        foreign_key="products.id", nullable=False, index=True, ondelete="CASCADE"
    )
    component_product_id: UUID | None = Field(
        default=None,
        foreign_key="products.id",
        nullable=True,
        index=True,
        ondelete="RESTRICT",
    )
    component_raw_material_id: UUID | None = Field(
        default=None,
        foreign_key="raw_materials.id",
        nullable=True,
        index=True,
        ondelete="RESTRICT",
    )
    quantity_per_unit: Decimal = Field(sa_type=Numeric(14, 3), nullable=False)
    position: int = Field(default=0, nullable=False)
