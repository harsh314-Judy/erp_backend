from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, Text
from sqlmodel import Field

from app.db.base import Entity


class Notification(Entity, table=True):
    __tablename__ = "notifications"

    user_id: UUID = Field(
        foreign_key="users.id", nullable=False, index=True, ondelete="CASCADE"
    )
    title: str = Field(max_length=180, nullable=False)
    body: str = Field(sa_type=Text, nullable=False)
    kind: str = Field(max_length=32, nullable=False, index=True)
    link: str | None = Field(default=None, max_length=255, nullable=True)
    read_at: datetime | None = Field(default=None, sa_type=DateTime(timezone=True), nullable=True)
