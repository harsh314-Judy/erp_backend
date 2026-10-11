from uuid import UUID

from sqlalchemy import Text
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
    quantity: int = Field(nullable=False)
    per_unit_price: int = Field(nullable=False)
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
    quantity: int = Field(nullable=False)
    per_unit_price: int = Field(nullable=False)
    note: str | None = Field(default=None, sa_type=Text, nullable=True)
    status: bool = Field(default=False, nullable=False)
