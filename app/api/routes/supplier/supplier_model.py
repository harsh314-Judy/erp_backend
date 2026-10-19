from uuid import UUID

from sqlalchemy import Text, UniqueConstraint
from sqlmodel import Field

from app.db.base import Entity


class Supplier(Entity, table=True):
    __tablename__ = "suppliers"

    supplier_company_name: str = Field(max_length=255, nullable=False, index=True)
    contact_person_name: str = Field(max_length=150, nullable=False)
    phone: str = Field(max_length=20, nullable=False)
    email: str = Field(max_length=255, nullable=False, index=True)
    is_gst: bool = Field(default=False, nullable=False)
    gst_number: str | None = Field(default=None, max_length=20, nullable=True)
    address: str = Field(sa_type=Text, nullable=False)
    alt_number: str | None = Field(default=None, max_length=20, nullable=True)
    supply_kind: str = Field(default="both", max_length=16, nullable=False)


class RawMaterialSupplier(Entity, table=True):
    __tablename__ = "raw_material_suppliers"
    __table_args__ = (
        UniqueConstraint(
            "raw_material_id",
            "supplier_id",
            name="uq_raw_material_supplier",
        ),
    )

    raw_material_id: UUID = Field(
        foreign_key="raw_materials.id",
        nullable=False,
        index=True,
        ondelete="CASCADE",
    )
    supplier_id: UUID = Field(
        foreign_key="suppliers.id",
        nullable=False,
        index=True,
        ondelete="CASCADE",
    )
    current_count: int = Field(default=0, nullable=False)


class ProductSupplier(Entity, table=True):
    __tablename__ = "product_suppliers"
    __table_args__ = (
        UniqueConstraint("product_id", "supplier_id", name="uq_product_supplier"),
    )

    product_id: UUID = Field(
        foreign_key="products.id",
        nullable=False,
        index=True,
        ondelete="CASCADE",
    )
    supplier_id: UUID = Field(
        foreign_key="suppliers.id",
        nullable=False,
        index=True,
        ondelete="CASCADE",
    )
    current_count: int = Field(default=0, nullable=False)
