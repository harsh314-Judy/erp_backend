from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field


class WorkerWrite(BaseModel):
    name: str = Field(min_length=1, max_length=120)


class WorkerPatch(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    active: bool | None = None


class WorkerRead(BaseModel):
    id: UUID
    operation_id: UUID
    name: str
    active: bool


class DepartmentInput(BaseModel):
    item_name: str
    planned_quantity: Decimal


class DepartmentActive(BaseModel):
    job_id: UUID
    product_name: str | None
    quantity: Decimal
    started_at: datetime | None
    due_at: datetime | None
    inputs: list[DepartmentInput]


class DepartmentRecent(BaseModel):
    worker_name: str | None
    product_name: str | None
    quantity: Decimal
    completed_at: datetime | None
    polish_type: str | None


class WorkerCount(BaseModel):
    name: str
    stages: int


class DepartmentRead(BaseModel):
    operation_id: UUID
    name: str
    workers: list[WorkerRead]
    active: list[DepartmentActive]
    recent: list[DepartmentRecent]
    per_worker: list[WorkerCount]
