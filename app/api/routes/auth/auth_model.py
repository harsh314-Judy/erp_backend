from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, Text
from sqlmodel import Field

from app.db.base import Entity


class UserInvite(Entity, table=True):
    """Invite-only account creation. Public signup is not supported."""

    __tablename__ = "user_invites"

    email: str = Field(max_length=255, nullable=False, index=True)
    first_name: str = Field(max_length=150, nullable=False)
    last_name: str | None = Field(default=None, max_length=150, nullable=True)
    role_id: UUID = Field(
        foreign_key="roles.id",
        nullable=False,
        index=True,
        ondelete="RESTRICT",
    )
    token_hash: str = Field(max_length=64, unique=True, nullable=False, index=True)
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
    token_hash: str = Field(max_length=64, unique=True, nullable=False, index=True)
    client_ip_hash: str = Field(max_length=64, nullable=False)
    expiry_date: datetime = Field(
        sa_type=DateTime(timezone=True),
        nullable=False,
    )
    rotated_at: datetime | None = Field(
        default=None,
        sa_type=DateTime(timezone=True),
        nullable=True,
    )
    replaced_by_hash: str | None = Field(default=None, max_length=64, nullable=True)
    # Raw successor kept only until the reuse grace window ends.
    successor_token: str | None = Field(default=None, sa_type=Text, nullable=True)


class ForgotPasswordToken(Entity, table=True):
    __tablename__ = "forgot_password_tokens"

    user_id: UUID = Field(
        foreign_key="users.id",
        nullable=False,
        index=True,
        ondelete="CASCADE",
    )
    token_hash: str = Field(max_length=64, unique=True, nullable=False, index=True)
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
    token_hash: str = Field(max_length=64, unique=True, nullable=False, index=True)
    expiry_date: datetime = Field(
        sa_type=DateTime(timezone=True),
        nullable=False,
    )
    number_of_time: int = Field(default=0, nullable=False)


class AuthRateLimit(Entity, table=True):
    __tablename__ = "auth_rate_limits"

    user_id: UUID | None = Field(
        default=None,
        foreign_key="users.id",
        nullable=True,
        index=True,
        ondelete="CASCADE",
    )
    client_ip_hash: str | None = Field(default=None, max_length=64, nullable=True, index=True)
    action: str = Field(max_length=64, nullable=False, index=True)
    window_start: datetime = Field(
        sa_type=DateTime(timezone=True),
        nullable=False,
    )
    count: int = Field(default=0, nullable=False)
    locked_until: datetime | None = Field(
        default=None,
        sa_type=DateTime(timezone=True),
        nullable=True,
    )
