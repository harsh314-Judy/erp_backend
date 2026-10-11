from uuid import UUID

from sqlmodel import Field

from app.db.base import Entity


class Role(Entity, table=True):
    __tablename__ = "roles"

    role_name: str = Field(max_length=100, unique=True, nullable=False, index=True)


class User(Entity, table=True):
    __tablename__ = "users"

    first_name: str = Field(max_length=150, nullable=False)
    last_name: str | None = Field(default=None, max_length=150, nullable=True)
    email: str = Field(max_length=255, unique=True, nullable=False, index=True)
    password: str = Field(max_length=255, nullable=False)
    role_id: UUID = Field(
        foreign_key="roles.id",
        nullable=False,
        index=True,
        ondelete="RESTRICT",
    )
