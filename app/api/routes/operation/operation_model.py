from uuid import UUID

from sqlalchemy import Text, UniqueConstraint
from sqlmodel import Field

from app.db.base import Entity


class Operation(Entity, table=True):
    __tablename__ = "operations"

    name: str = Field(max_length=150, unique=True, nullable=False, index=True)
    description: str | None = Field(default=None, sa_type=Text, nullable=True)


class UserOperation(Entity, table=True):
    __tablename__ = "user_operations"
    __table_args__ = (
        UniqueConstraint("operation_id", "user_id", name="uq_user_operation"),
    )

    operation_id: UUID = Field(
        foreign_key="operations.id",
        nullable=False,
        index=True,
        ondelete="CASCADE",
    )
    user_id: UUID = Field(
        foreign_key="users.id",
        nullable=False,
        index=True,
        ondelete="CASCADE",
    )
