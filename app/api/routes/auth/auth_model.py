from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime
from sqlmodel import Field

from app.db.base import Entity


class UserInvite(Entity, table=True):
    """Invite-only account creation. Public signup is not supported."""

    __tablename__ = "user_invites"

    email: str = Field(max_length=255, nullable=False, index=True)
    role_id: UUID = Field(
        foreign_key="roles.id",
        nullable=False,
        index=True,
        ondelete="RESTRICT",
    )
    token: str = Field(max_length=512, unique=True, nullable=False, index=True)
    expiry_date: datetime = Field(
        sa_type=DateTime(timezone=True),
        nullable=False,
    )
    invited_by_user_id: UUID | None = Field(
        default=None,
        foreign_key="users.id",
        nullable=True,
        index=True,
        ondelete="SET NULL",
    )
    accepted_at: datetime | None = Field(
        default=None,
        sa_type=DateTime(timezone=True),
        nullable=True,
    )


class RefreshToken(Entity, table=True):
    __tablename__ = "refresh_tokens"

    user_id: UUID = Field(
        foreign_key="users.id",
        nullable=False,
        index=True,
        ondelete="CASCADE",
    )
    token: str = Field(max_length=512, unique=True, nullable=False, index=True)
    expiry_date: datetime = Field(
        sa_type=DateTime(timezone=True),
        nullable=False,
    )


class ForgotPasswordToken(Entity, table=True):
    __tablename__ = "forgot_password_tokens"

    user_id: UUID = Field(
        foreign_key="users.id",
        nullable=False,
        index=True,
        ondelete="CASCADE",
    )
    token: str = Field(max_length=512, unique=True, nullable=False, index=True)
    expiry_date: datetime = Field(
        sa_type=DateTime(timezone=True),
        nullable=False,
    )
    number_of_time: int = Field(default=0, nullable=False)


class ResetPasswordToken(Entity, table=True):
    __tablename__ = "reset_password_tokens"

    user_id: UUID = Field(
        foreign_key="users.id",
        nullable=False,
        index=True,
        ondelete="CASCADE",
    )
    token: str = Field(max_length=512, unique=True, nullable=False, index=True)
    expiry_date: datetime = Field(
        sa_type=DateTime(timezone=True),
        nullable=False,
    )
    number_of_time: int = Field(default=0, nullable=False)
