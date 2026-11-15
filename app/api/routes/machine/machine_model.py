from uuid import UUID

from sqlalchemy import Text
from sqlmodel import Field

from app.db.base import Entity


class Machine(Entity, table=True):
    __tablename__ = "machines"

    name: str = Field(max_length=120, nullable=False)
    operation_id: UUID = Field(
        foreign_key="operations.id",
        nullable=False,
        index=True,
        ondelete="RESTRICT",
    )
    status: str = Field(default="up", max_length=8, nullable=False, index=True)
    note: str | None = Field(default=None, sa_type=Text, nullable=True)
