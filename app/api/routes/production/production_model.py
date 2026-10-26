from datetime import datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import DateTime, Numeric, Text
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
    quantity: Decimal = Field(default=Decimal("0"), sa_type=Numeric(14, 3), nullable=False)
    status: str = Field(default="pending", max_length=32, nullable=False, index=True)
    estimated_minutes: int = Field(default=0, nullable=False)
    due_at: datetime | None = Field(default=None, sa_type=DateTime(timezone=True), nullable=True)
    started_at: datetime | None = Field(
        default=None, sa_type=DateTime(timezone=True), nullable=True
    )
    completed_at: datetime | None = Field(
        default=None, sa_type=DateTime(timezone=True), nullable=True
    )
    source: str = Field(default="manual", max_length=32, nullable=False)
    source_id: UUID | None = Field(default=None, nullable=True, index=True)
    created_by_user_id: UUID | None = Field(
        default=None,
        foreign_key="users.id",
        nullable=True,
        index=True,
        ondelete="SET NULL",
    )
    cancellation_reason: str | None = Field(default=None, sa_type=Text, nullable=True)
    produced_quantity: Decimal = Field(
        default=Decimal("0"), sa_type=Numeric(14, 3), nullable=False
    )


class ProductionJobStage(Entity, table=True):
    __tablename__ = "production_job_stages"

    job_id: UUID = Field(
        foreign_key="production_jobs.id", nullable=False, index=True, ondelete="CASCADE"
    )
    operation_id: UUID = Field(
        foreign_key="operations.id", nullable=False, index=True, ondelete="RESTRICT"
    )
    position: int = Field(nullable=False)
    assigned_user_id: UUID | None = Field(
        default=None,
        foreign_key="users.id",
        nullable=True,
        index=True,
        ondelete="SET NULL",
    )
    status: str = Field(default="pending", max_length=32, nullable=False)
    polish_type: str | None = Field(default=None, max_length=16, nullable=True)
    notes: str | None = Field(default=None, sa_type=Text, nullable=True)
    started_at: datetime | None = Field(
        default=None, sa_type=DateTime(timezone=True), nullable=True
    )
    completed_at: datetime | None = Field(
        default=None, sa_type=DateTime(timezone=True), nullable=True
    )


class ProductionJobInput(Entity, table=True):
    __tablename__ = "production_job_inputs"

    job_id: UUID = Field(
        foreign_key="production_jobs.id", nullable=False, index=True, ondelete="CASCADE"
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
    planned_quantity: Decimal = Field(sa_type=Numeric(14, 3), nullable=False)
    actual_quantity: Decimal | None = Field(default=None, sa_type=Numeric(14, 3), nullable=True)
    wastage_quantity: Decimal = Field(default=Decimal("0"), sa_type=Numeric(14, 3), nullable=False)
    reservation_id: UUID | None = Field(default=None, nullable=True)
