from uuid import UUID

from sqlalchemy import Text
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
    quantity: int = Field(default=0, nullable=False)
    gst: bool = Field(default=False, nullable=False)
    measurement_unit_id: UUID = Field(
        foreign_key="measurement_units.id",
        nullable=False,
        index=True,
        ondelete="RESTRICT",
    )
    sale_price_without_gst: int = Field(nullable=False)
    description: str | None = Field(default=None, sa_type=Text, nullable=True)
    gst_percent: int = Field(default=0, nullable=False)
    category_id: UUID = Field(
        foreign_key="product_categories.id",
        nullable=False,
        index=True,
        ondelete="RESTRICT",
    )
    alert_quantity: int = Field(default=0, nullable=False)
    quantity_per_bundle: int = Field(default=1, nullable=False)
