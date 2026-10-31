from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ProductionJobCreate(BaseModel):
    product_id: UUID
    quantity: Decimal = Field(gt=0)
    notes: str | None = None
    estimated_minutes: int = Field(ge=1)
    operation_ids: list[UUID] | None = None
    source: str = "manual"
    source_id: UUID | None = None
    deadline: datetime | None = None
    assigned_user_id: UUID | None = None


class ProductionJobUpdate(BaseModel):
    quantity: Decimal | None = Field(default=None, gt=0)
    notes: str | None = None
    estimated_minutes: int | None = Field(default=None, ge=1)
    deadline: datetime | None = None
    assigned_user_id: UUID | None = None


class StageComplete(BaseModel):
    polish_type: str | None = None
    notes: str | None = None


class StageRevert(BaseModel):
    note: str = Field(min_length=3)


class RequirementLine(BaseModel):
    input_id: UUID
    planned_quantity: Decimal = Field(ge=0)


class RequirementUpdate(BaseModel):
    note: str = Field(min_length=3)
    inputs: list[RequirementLine] = Field(min_length=1)


class VarianceCreate(BaseModel):
    kind: str = Field(pattern="^(waste|extra_used|extra_made)$")
    item_name: str = Field(min_length=1, max_length=120)
    quantity: Decimal = Field(gt=0)
    note: str = Field(min_length=3)


class JobEvent(BaseModel):
    at: datetime
    user_name: str
    action: str
    stage: str | None = None
    detail: str


class VarianceRead(BaseModel):
    at: datetime
    user_name: str
    kind: str
    item_name: str
    quantity: str
    note: str
    stage: str | None = None


class InputActual(BaseModel):
    input_id: UUID
    actual_quantity: Decimal = Field(ge=0)
    wastage_quantity: Decimal = Field(default=Decimal("0"), ge=0)


class JobApprove(BaseModel):
    produced_quantity: Decimal = Field(ge=0)
    inputs: list[InputActual]


class JobCancel(BaseModel):
    reason: str = Field(min_length=3)
    produced_quantity: Decimal = Field(default=Decimal("0"), ge=0)
    inputs: list[InputActual] = Field(default_factory=list)


class StageRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    operation_id: UUID
    operation_name: str | None = None
    position: int
    assigned_user_id: UUID | None
    status: str
    polish_type: str | None
    notes: str | None
    started_at: datetime | None = None
    completed_at: datetime | None = None


class InputRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    product_id: UUID | None
    raw_material_id: UUID | None
    item_name: str | None = None
    planned_quantity: Decimal
    actual_quantity: Decimal | None
    wastage_quantity: Decimal
    available: Decimal | None = None


class ProductionJobRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    product_id: UUID
    product_name: str | None = None
    quantity: Decimal
    status: str
    notes: str | None
    estimated_minutes: int
    due_at: datetime | None
    started_at: datetime | None
    source: str
    overdue: bool = False
    current_operation_name: str | None = None
    produced_quantity: Decimal = Decimal("0")
    created_at: datetime | None = None
    created_by_name: str | None = None
    assigned_user_id: UUID | None = None
    assigned_user_name: str | None = None


class ProductionJobDetail(ProductionJobRead):
    stages: list[StageRead]
    inputs: list[InputRead]
    cancellation_reason: str | None = None
    created_at: datetime | None = None
    created_by_name: str | None = None
    events: list[JobEvent] = Field(default_factory=list)
    variances: list[VarianceRead] = Field(default_factory=list)
