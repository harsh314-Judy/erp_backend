from datetime import date, datetime
from uuid import UUID

from sqlalchemy import Boolean, Date, DateTime, Index, Integer, false
from sqlmodel import Field, SQLModel

from app.db.base import new_id, utcnow


class ActivityLog(SQLModel, table=True):
    """One short row per meaningful action. The person name is copied so a year of history stays after an account is removed."""

    __tablename__ = "activity_logs"
    __table_args__ = (Index("ix_activity_logs_role_created", "role_name", "created_at"),)

    id: UUID = Field(default_factory=new_id, primary_key=True)
    created_at: datetime = Field(
        default_factory=utcnow,
        sa_type=DateTime(timezone=True),
        nullable=False,
        index=True,
    )
    user_id: UUID | None = Field(
        default=None,
        foreign_key="users.id",
        nullable=True,
        index=True,
        ondelete="SET NULL",
    )
    person: str = Field(max_length=160, nullable=False)
    role_name: str = Field(max_length=32, nullable=False, index=True)
    action: str = Field(max_length=32, nullable=False)
    summary: str = Field(max_length=160, nullable=False)
    ip: str | None = Field(default=None, max_length=45, nullable=True)
    browser: str | None = Field(default=None, max_length=48, nullable=True)
    os_name: str | None = Field(default=None, max_length=48, nullable=True)
    device_type: str | None = Field(default=None, max_length=16, nullable=True)
    device_model: str | None = Field(default=None, max_length=80, nullable=True)


class StaffPresence(SQLModel, table=True):
    """Current floor state. One row per person, updated in place so it does not grow over the year."""

    __tablename__ = "staff_presence"

    user_id: UUID = Field(foreign_key="users.id", primary_key=True, ondelete="CASCADE")
    on_break: bool = Field(
        default=False,
        sa_type=Boolean(),
        nullable=False,
        sa_column_kwargs={"server_default": false()},
    )
    break_started_at: datetime | None = Field(
        default=None,
        sa_type=DateTime(timezone=True),
        nullable=True,
    )
    last_login_at: datetime | None = Field(
        default=None,
        sa_type=DateTime(timezone=True),
        nullable=True,
    )
    last_seen_at: datetime | None = Field(
        default=None,
        sa_type=DateTime(timezone=True),
        nullable=True,
    )
    device_label: str | None = Field(default=None, max_length=120, nullable=True)
    break_used_seconds: int = Field(
        default=0,
        sa_type=Integer(),
        nullable=False,
        sa_column_kwargs={"server_default": "0"},
    )
    break_day: date | None = Field(default=None, sa_type=Date(), nullable=True)
