from uuid import UUID

from sqlalchemy import Boolean, false
from sqlmodel import Field

from app.db.base import Entity

# Fixed roles. Responsibilities for each one are assigned later.
SYSTEM_ROLES = ("super_admin", "admin", "accountant", "staff")
# Admin can edit identity for strictly lower roles. Super admin can edit every role.
MANAGED_BY_ADMIN = frozenset({"accountant", "staff"})


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
    # Set when a super admin takes over name or email. Nobody else can change them.
    identity_overridden: bool = Field(
        default=False,
        sa_type=Boolean(),
        nullable=False,
        sa_column_kwargs={"server_default": false()},
    )
