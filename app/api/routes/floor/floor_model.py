from datetime import date
from decimal import Decimal
from uuid import UUID

from sqlalchemy import Date, Index, Numeric, Text, UniqueConstraint
from sqlmodel import Field

from app.db.base import Entity


class FloorEntry(Entity, table=True):
    """One logbook line: what a department made, used, and scrapped on a day."""

    __tablename__ = "floor_entries"
    __table_args__ = (Index("ix_floor_entries_operation_date", "operation_id", "entry_date"),)

    entry_date: date = Field(sa_type=Date, nullable=False, index=True)
    operation_id: UUID = Field(
        foreign_key="operations.id", nullable=False, index=True, ondelete="RESTRICT"
    )
    output_product_id: UUID | None = Field(
        default=None, foreign_key="products.id", nullable=True, ondelete="RESTRICT"
    )
    output_name: str = Field(max_length=255, nullable=False)
    output_quantity: Decimal = Field(default=Decimal("0"), sa_type=Numeric(14, 3), nullable=False)
    output_unit: str = Field(max_length=16, nullable=False)
    input_product_id: UUID | None = Field(
        default=None, foreign_key="products.id", nullable=True, ondelete="RESTRICT"
    )
    input_raw_material_id: UUID | None = Field(
        default=None, foreign_key="raw_materials.id", nullable=True, ondelete="RESTRICT"
    )
    input_name: str | None = Field(default=None, max_length=255, nullable=True)
    input_quantity: Decimal | None = Field(default=None, sa_type=Numeric(14, 3), nullable=True)
    input_unit: str | None = Field(default=None, max_length=16, nullable=True)
    scrap_quantity: Decimal = Field(default=Decimal("0"), sa_type=Numeric(14, 3), nullable=False)
    scrap_unit: str | None = Field(default=None, max_length=16, nullable=True)
    notes: str | None = Field(default=None, sa_type=Text, nullable=True)
    job_id: UUID | None = Field(
        default=None, foreign_key="production_jobs.id", nullable=True, index=True, ondelete="SET NULL"
    )
    stage_id: UUID | None = Field(
        default=None,
        foreign_key="production_job_stages.id",
        nullable=True,
        unique=True,
        ondelete="SET NULL",
    )
    created_by_user_id: UUID | None = Field(
        default=None, foreign_key="users.id", nullable=True, ondelete="SET NULL"
    )


class FloorEntryWorker(Entity, table=True):
    """People credited for a logbook line. A shared batch credits each of them in full."""

    __tablename__ = "floor_entry_workers"
    __table_args__ = (UniqueConstraint("entry_id", "worker_id", name="uq_floor_entry_worker"),)

    entry_id: UUID = Field(
        foreign_key="floor_entries.id", nullable=False, index=True, ondelete="CASCADE"
    )
    worker_id: UUID = Field(
        foreign_key="department_workers.id", nullable=False, index=True, ondelete="RESTRICT"
    )
    worker_name: str = Field(max_length=120, nullable=False)
