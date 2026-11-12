from datetime import date, datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field


class UnitTotal(BaseModel):
    unit: str
    quantity: Decimal


class ScrapRate(BaseModel):
    unit: str
    percent: Decimal | None


class EntryWorker(BaseModel):
    id: UUID
    name: str


class FloorEntryWrite(BaseModel):
    entry_date: date
    operation_id: UUID
    worker_ids: list[UUID] = Field(min_length=1, max_length=3)
    output_name: str = Field(min_length=1, max_length=255)
    output_quantity: Decimal = Field(ge=0)
    output_unit: str = Field(min_length=1, max_length=16)
    output_product_id: UUID | None = None
    input_name: str | None = Field(default=None, max_length=255)
    input_quantity: Decimal | None = Field(default=None, ge=0)
    input_unit: str | None = Field(default=None, max_length=16)
    input_product_id: UUID | None = None
    input_raw_material_id: UUID | None = None
    scrap_quantity: Decimal = Field(default=Decimal("0"), ge=0)
    scrap_unit: str | None = Field(default=None, max_length=16)
    notes: str | None = None


class FloorEntryRead(BaseModel):
    id: UUID
    entry_date: date
    operation_id: UUID
    operation_name: str
    workers: list[EntryWorker]
    output_name: str
    output_quantity: Decimal
    output_unit: str
    output_product_id: UUID | None
    input_name: str | None
    input_quantity: Decimal | None
    input_unit: str | None
    input_product_id: UUID | None
    input_raw_material_id: UUID | None
    scrap_quantity: Decimal
    scrap_unit: str | None
    notes: str | None
    from_job: bool
    job_id: UUID | None
    created_by_name: str | None
    created_at: datetime


class PersonTotal(BaseModel):
    worker_id: UUID
    name: str
    made: list[UnitTotal]


class DepartmentSummary(BaseModel):
    operation_id: UUID
    name: str
    entries: int
    workers: int
    open_jobs: int
    output: list[UnitTotal]
    used: list[UnitTotal]
    scrap: list[UnitTotal]
    scrap_pct: list[ScrapRate]
    people: list[PersonTotal]


class FloorSummary(BaseModel):
    date_from: date
    date_to: date
    departments: list[DepartmentSummary]


class HistorySpan(BaseModel):
    operation_id: UUID
    operation_name: str
    started_on: date
    ended_on: date | None


class WorkerNow(BaseModel):
    department: str | None
    last_entry_at: datetime | None
    today_entries: int
    open_jobs_in_department: int


class DailyPoint(BaseModel):
    date: date
    unit: str
    output: Decimal
    scrap: Decimal
    entries: int


class ItemTotal(BaseModel):
    name: str
    unit: str
    output: Decimal
    scrap: Decimal
    entries: int


class FeedItem(BaseModel):
    at: datetime
    kind: Literal["entry", "move"]
    title: str
    detail: str
    shared_with: list[str]


class WorkerTimeline(BaseModel):
    worker_id: UUID
    name: str
    active: bool
    employment_type: str
    phone: str | None
    address: str | None
    emergency_contact_name: str | None
    emergency_contact_phone: str | None
    operation_id: UUID
    operation_name: str
    date_from: date
    date_to: date
    history: list[HistorySpan]
    now: WorkerNow
    output: list[UnitTotal]
    used: list[UnitTotal]
    scrap: list[UnitTotal]
    scrap_pct: list[ScrapRate]
    active_days: int
    avg_per_active_day: list[UnitTotal]
    shared_entries: int
    department_avg_per_worker_day: list[UnitTotal]
    daily: list[DailyPoint]
    items: list[ItemTotal]
    feed: list[FeedItem]
