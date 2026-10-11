from uuid import UUID

from sqlalchemy import Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field

from app.db.base import Entity


class ProductionJob(Entity, table=True):
    __tablename__ = "production_jobs"

    product_id: UUID = Field(
        foreign_key="products.id",
        nullable=False,
        index=True,
        ondelete="RESTRICT",
    )
    current_operation_id: UUID = Field(
        foreign_key="operations.id",
        nullable=False,
        index=True,
        ondelete="RESTRICT",
    )
    notes: str | None = Field(default=None, sa_type=Text, nullable=True)
    raw_material_used: dict = Field(default_factory=dict, sa_type=JSONB, nullable=False)
    operation_flow: dict = Field(default_factory=dict, sa_type=JSONB, nullable=False)
    product_used: dict = Field(default_factory=dict, sa_type=JSONB, nullable=False)
    quantity: int = Field(default=0, nullable=False)
    raw_material_used_after_production: dict = Field(
        default_factory=dict,
        sa_type=JSONB,
        nullable=False,
    )
    product_used_after_production: dict = Field(
        default_factory=dict,
        sa_type=JSONB,
        nullable=False,
    )
