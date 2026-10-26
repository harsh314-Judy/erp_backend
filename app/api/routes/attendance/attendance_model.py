from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, Index
from sqlmodel import Field, SQLModel

from app.db.base import new_id


class Attendance(SQLModel, table=True):
    """One row per sign-in. Sign-out fills the empty end time. The name is copied so the row survives account removal."""

    __tablename__ = "attendance"
    __table_args__ = (Index("ix_attendance_signed_in", "signed_in_at"),)

    id: UUID = Field(default_factory=new_id, primary_key=True)
    user_id: UUID | None = Field(
        default=None,
        foreign_key="users.id",
        nullable=True,
        index=True,
        ondelete="SET NULL",
    )
    person: str = Field(max_length=160, nullable=False)
    role_name: str = Field(max_length=32, nullable=False)
    signed_in_at: datetime = Field(sa_type=DateTime(timezone=True), nullable=False)
    signed_out_at: datetime | None = Field(
        default=None,
        sa_type=DateTime(timezone=True),
        nullable=True,
    )
