from datetime import date
from decimal import Decimal
from uuid import UUID

from sqlalchemy import Date, Numeric, Text, UniqueConstraint
from sqlmodel import Field

from app.db.base import Entity


class DepartmentWorker(Entity, table=True):
    """One person. operation_id is the department they work in right now."""

    __tablename__ = "department_workers"
    __table_args__ = (UniqueConstraint("operation_id", "name", name="uq_department_worker_name"),)

    operation_id: UUID = Field(
        foreign_key="operations.id", nullable=False, index=True, ondelete="CASCADE"
    )
    name: str = Field(max_length=120, nullable=False)
    active: bool = Field(default=True, nullable=False)
    phone: str | None = Field(default=None, max_length=20, nullable=True)
    employment_type: str = Field(default="permanent", max_length=16, nullable=False)
    address: str | None = Field(default=None, sa_type=Text, nullable=True)
    emergency_contact_name: str | None = Field(default=None, max_length=120, nullable=True)
    emergency_contact_phone: str | None = Field(default=None, max_length=20, nullable=True)
    wage_kind: str = Field(default="daily", max_length=16, nullable=False)
    wage_amount: Decimal = Field(default=Decimal("0"), sa_type=Numeric(12, 2), nullable=False)


class WorkerDepartmentHistory(Entity, table=True):
    """Each stretch a person spent in a department. ended_on is empty while they are still there."""

    __tablename__ = "worker_department_history"

    worker_id: UUID = Field(
        foreign_key="department_workers.id", nullable=False, index=True, ondelete="CASCADE"
    )
    operation_id: UUID = Field(
        foreign_key="operations.id", nullable=False, index=True, ondelete="RESTRICT"
    )
    started_on: date = Field(sa_type=Date, nullable=False)
    ended_on: date | None = Field(default=None, sa_type=Date, nullable=True)


class FloorDay(Entity, table=True):
    """One mark for one floor person on one Asia/Kolkata date. Not a sign-in row."""

    __tablename__ = "floor_days"
    __table_args__ = (UniqueConstraint("worker_id", "work_date", name="uq_floor_day"),)

    worker_id: UUID = Field(
        foreign_key="department_workers.id", nullable=False, index=True, ondelete="CASCADE"
    )
    work_date: date = Field(sa_type=Date, nullable=False)
    status: str = Field(max_length=16, nullable=False)


class WorkerMonthPay(Entity, table=True):
    """The single already-given amount for one person in one month."""

    __tablename__ = "worker_month_pay"
    __table_args__ = (UniqueConstraint("worker_id", "year", "month", name="uq_worker_month_pay"),)

    worker_id: UUID = Field(
        foreign_key="department_workers.id", nullable=False, index=True, ondelete="CASCADE"
    )
    year: int = Field(nullable=False)
    month: int = Field(nullable=False)
    already_given: Decimal = Field(default=Decimal("0"), sa_type=Numeric(12, 2), nullable=False)
