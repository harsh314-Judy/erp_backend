from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class VisitCreate(BaseModel):
    module: str = Field(min_length=1, max_length=40)


class BreakUpdate(BaseModel):
    on_break: bool


class BreakAllowanceUpdate(BaseModel):
    minutes: int | None = None


class BreakRosterItem(BaseModel):
    user_id: UUID
    person: str
    role_name: str | None
    email: str
    minutes: int | None


class PresenceRead(BaseModel):
    on_break: bool
    break_started_at: datetime | None
    last_login_at: datetime | None
    last_seen_at: datetime | None
    device_label: str | None
    break_allowance_minutes: int | None = None
    break_used_seconds: int = 0


class PersonStatus(PresenceRead):
    user_id: UUID


class ActivityEvent(BaseModel):
    id: UUID
    user_id: UUID | None
    person: str
    role_name: str
    action: str
    summary: str
    browser: str | None
    os_name: str | None
    device_type: str | None
    device_model: str | None
    created_at: datetime


class ActivityBoard(BaseModel):
    seen_today: int
    people: list[PersonStatus]
    events: list[ActivityEvent]
