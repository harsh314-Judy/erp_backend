from datetime import date, datetime
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
    wage_kind: str | None = Field(default=None, pattern="^(daily|monthly)$")
    wage_amount: Decimal | None = Field(default=None, ge=0)


class WorkerPatch(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    active: bool | None = None
    phone: str | None = Field(default=None, max_length=20)
    employment_type: str | None = Field(default=None, pattern="^(permanent|temporary)$")
    address: str | None = None
    emergency_contact_name: str | None = Field(default=None, max_length=120)
    emergency_contact_phone: str | None = Field(default=None, max_length=20)
    operation_id: UUID | None = None
    wage_kind: str | None = Field(default=None, pattern="^(daily|monthly)$")
    wage_amount: Decimal | None = Field(default=None, ge=0)


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
    wage_kind: str | None = None
    wage_amount: Decimal | None = None


class DepartmentInput(BaseModel):
    input_id: UUID | None = None
    item_name: str
    planned_quantity: Decimal
    kind: str | None = None
    taken_quantity: Decimal = Decimal("0")


class DepartmentActive(BaseModel):
    job_id: UUID
    stage_id: UUID
    product_name: str | None
    quantity: Decimal
    good_quantity: Decimal = Decimal("0")
    scrap_quantity: Decimal = Decimal("0")
    remaining: Decimal = Decimal("0")
    job_status: str = "in_progress"
    problem_reason: str | None = None
    problem_note: str | None = None
    problem_machine_name: str | None = None
    worker_name: str | None = None
    bundle_size: Decimal | None = None
    started_at: datetime | None
    due_at: datetime | None
    inputs: list[DepartmentInput]
    allows_send_out: bool = False
    standard_scrap_percent: Decimal | None = None
    outside: list["OutsideOpen"] = Field(default_factory=list)
    sends: list["DeskSend"] = Field(default_factory=list)


class OutsideOpen(BaseModel):
    supplier_name: str
    quantity: Decimal


class DeskSend(BaseModel):
    id: UUID
    supplier_id: UUID
    supplier_name: str
    quantity: Decimal
    sent_on: date
    good_quantity: Decimal
    rejected_quantity: Decimal
    still_out: Decimal


DepartmentActive.model_rebuild()


class DepartmentRecent(BaseModel):
    worker_name: str | None
    product_name: str | None
    quantity: Decimal
    scrap_quantity: Decimal = Decimal("0")
    notes: str | None = None
    unit: str | None = None
    completed_at: datetime | None
    polish_type: str | None = None
    shared: bool = False


class AssignedDepartment(BaseModel):
    operation_id: UUID
    name: str


class WorkerCount(BaseModel):
    worker_id: UUID | None = None
    name: str
    stages: int
    made: list[UnitTotal] = []


class DepartmentMachine(BaseModel):
    id: UUID
    name: str
    status: str
    note: str | None = None


class DepartmentRead(BaseModel):
    operation_id: UUID
    name: str
    workers: list[WorkerRead]
    machines: list[DepartmentMachine] = []
    active: list[DepartmentActive]
    recent: list[DepartmentRecent]
    per_worker: list[WorkerCount]
    output: list[UnitTotal] = []
    used: list[UnitTotal] = []
    scrap: list[UnitTotal] = []
