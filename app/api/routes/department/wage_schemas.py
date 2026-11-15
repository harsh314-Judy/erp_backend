from datetime import date
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field


class DayMark(BaseModel):
    worker_id: UUID
    work_date: date
    status: str | None = Field(default=None, pattern="^(present|absent|half)$")


class AdvanceWrite(BaseModel):
    worker_id: UUID
    year: int = Field(ge=2000, le=2100)
    month: int = Field(ge=1, le=12)
    already_given: Decimal = Field(ge=0)


class WageDay(BaseModel):
    work_date: date
    status: str


class WagePerson(BaseModel):
    worker_id: UUID
    name: str
    operation_name: str
    active: bool
    wage_kind: str
    wage_amount: Decimal
    present_days: int
    half_days: int
    absent_dates: list[date]
    days: list[WageDay]
    already_given: Decimal
    owed: Decimal


class WageMonth(BaseModel):
    year: int
    month: int
    people: list[WagePerson]
    total_owed: Decimal


class WageOwed(BaseModel):
    year: int
    month: int
    total_owed: Decimal
