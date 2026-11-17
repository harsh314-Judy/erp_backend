from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, Text
from sqlmodel import Field

from app.db.base import Entity, utcnow


class ActivityEvent(Entity, table=True):
    __tablename__ = "activity_events"

    occurred_at: datetime = Field(
        default_factory=utcnow,
        sa_type=DateTime(timezone=True),
        nullable=False,
        index=True,
    )
    kind: str = Field(max_length=32, nullable=False, index=True)
    summary: str = Field(sa_type=Text, nullable=False)
    ref_type: str = Field(max_length=32, nullable=False)
    ref_id: UUID | None = Field(default=None, nullable=True)
    actor_user_id: UUID | None = Field(
        default=None, foreign_key="users.id", nullable=True, ondelete="SET NULL"
    )
    link: str | None = Field(default=None, max_length=255, nullable=True)
