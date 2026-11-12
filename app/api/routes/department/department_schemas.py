from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field


class UnitTotal(BaseModel):
    unit: str
    quantity: Decimal


class WorkerWrite(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    phone: str | None = Field(default=None, max_length=20)
    employment_type: str = Field(default="permanent", pattern="^(permanent|temporary)$")
    address: str | None = None
    emergency_contact_name: str | None = Field(default=None, max_length=120)
    emergency_contact_phone: str | None = Field(default=None, max_length=20)


class WorkerPatch(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    active: bool | None = None
    phone: str | None = Field(default=None, max_length=20)
    employment_type: str | None = Field(default=None, pattern="^(permanent|temporary)$")
    address: str | None = None
    emergency_contact_name: str | None = Field(default=None, max_length=120)
    emergency_contact_phone: str | None = Field(default=None, max_length=20)
    operation_id: UUID | None = None


class WorkerRead(BaseModel):
    id: UUID
    operation_id: UUID
    operation_name: str = ""
    name: str
    active: bool
    employment_type: str = "permanent"
    phone: str | None = None
    address: str | None = None
    emergency_contact_name: str | None = None
    emergency_contact_phone: str | None = None


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
    unit: str | None = None
    completed_at: datetime | None
    polish_type: str | None = None
    shared: bool = False


class WorkerCount(BaseModel):
    worker_id: UUID | None = None
    name: str
    stages: int
    made: list[UnitTotal] = []


class DepartmentRead(BaseModel):
    operation_id: UUID
    name: str
    workers: list[WorkerRead]
    active: list[DepartmentActive]
    recent: list[DepartmentRecent]
    per_worker: list[WorkerCount]
    output: list[UnitTotal] = []
    used: list[UnitTotal] = []
    scrap: list[UnitTotal] = []
