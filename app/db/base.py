from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import DateTime, func
from sqlmodel import Field, SQLModel
from uuid6 import uuid7


def new_id() -> UUID:
    return uuid7()


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Entity(SQLModel):
    """Shared primary key and timestamps for every ERP table."""

    id: UUID = Field(default_factory=new_id, primary_key=True)
    created_at: datetime = Field(
        default_factory=utcnow,
        sa_type=DateTime(timezone=True),
        sa_column_kwargs={"server_default": func.now(), "nullable": False},
    )
    updated_at: datetime = Field(
        default_factory=utcnow,
        sa_type=DateTime(timezone=True),
        sa_column_kwargs={
            "server_default": func.now(),
            "onupdate": func.now(),
            "nullable": False,
        },
    )
