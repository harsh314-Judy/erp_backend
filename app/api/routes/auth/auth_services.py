import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from uuid import UUID

from fastapi import HTTPException, status
from jose import jwt
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.api.routes.auth.auth_model import (
    ForgotPasswordToken,
    RefreshToken,
    ResetPasswordToken,
    UserInvite,
)
from app.api.routes.auth.auth_schemas import (
    ForgotPasswordRequest,
    ForgotPasswordResponse,
    InviteCreate,
    InviteRead,
    LoginRequest,
    RefreshRequest,
    ResetPasswordRequest,
    SignupRequest,
    TokenResponse,
)
from app.api.routes.user.user_model import Role, User
from app.api.routes.user.user_schemas import UserRead
from app.api.schemas.common import MessageResponse
from app.config import auth_settings
from app.db.repository import commit_or_conflict, get_or_404


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode(),
        bytes.fromhex(salt),
        600_000,
    )
    return f"pbkdf2_sha256${salt}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        algorithm, salt, digest = stored.split("$", 2)
    except ValueError:
        return False
    if algorithm != "pbkdf2_sha256":
        return False
    check = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode(),
        bytes.fromhex(salt),
        600_000,
    )
    return secrets.compare_digest(check.hex(), digest)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _new_token() -> str:
    return secrets.token_urlsafe(32)


def _access_token(user_id: UUID) -> str:
    expires = _utcnow() + timedelta(minutes=auth_settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    return jwt.encode(
        {"sub": str(user_id), "exp": expires},
        auth_settings.JWT_SECRET,
        algorithm=auth_settings.JWT_ALGORITHM,
    )


class AuthService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create_invite(
        self,
        data: InviteCreate,
        invited_by_user_id: UUID | None = None,
    ) -> InviteRead:
        await get_or_404(self.session, Role, data.role_id)
        invite = UserInvite(
            email=data.email.strip().lower(),
            role_id=data.role_id,
            token=_new_token(),
            expiry_date=_utcnow() + timedelta(days=auth_settings.INVITE_EXPIRE_DAYS),
            invited_by_user_id=invited_by_user_id,
        )
        self.session.add(invite)
        await commit_or_conflict(self.session)
        await self.session.refresh(invite)
        return InviteRead.model_validate(invite)

    async def signup(self, data: SignupRequest) -> UserRead:
        invite = await self._active_invite(data.token)
        existing = await self.session.scalar(
            select(User).where(User.email == invite.email)
        )
        if existing is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="An account already exists for this invite",
            )
        user = User(
            first_name=data.first_name.strip(),
            last_name=data.last_name.strip() if data.last_name else None,
            email=invite.email,
            password=hash_password(data.password),
            role_id=invite.role_id,
        )
        invite.accepted_at = _utcnow()
        self.session.add(user)
        self.session.add(invite)
        await commit_or_conflict(self.session)
        await self.session.refresh(user)
        return UserRead.model_validate(user)

    async def login(self, data: LoginRequest) -> TokenResponse:
        email = data.email.strip().lower()
        user = await self.session.scalar(select(User).where(User.email == email))
        if user is None or not verify_password(data.password, user.password):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect email or password",
            )
        refresh = RefreshToken(
            user_id=user.id,
            token=_new_token(),
            expiry_date=_utcnow()
            + timedelta(days=auth_settings.REFRESH_TOKEN_EXPIRE_DAYS),
        )
        self.session.add(refresh)
        await commit_or_conflict(self.session)
        return TokenResponse(
            access_token=_access_token(user.id),
            refresh_token=refresh.token,
        )

    async def refresh(self, data: RefreshRequest) -> TokenResponse:
        row = await self.session.scalar(
            select(RefreshToken).where(RefreshToken.token == data.refresh_token)
        )
        if row is None or row.expiry_date < _utcnow():
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Refresh token is invalid or expired",
            )
        row.token = _new_token()
        row.expiry_date = _utcnow() + timedelta(
            days=auth_settings.REFRESH_TOKEN_EXPIRE_DAYS
        )
        self.session.add(row)
        await commit_or_conflict(self.session)
        return TokenResponse(
            access_token=_access_token(row.user_id),
            refresh_token=row.token,
        )

    async def forgot_password(self, data: ForgotPasswordRequest) -> ForgotPasswordResponse:
        email = data.email.strip().lower()
        user = await self.session.scalar(select(User).where(User.email == email))
        if user is None:
            return ForgotPasswordResponse(
                message="If the account exists, a reset token has been created"
            )
        token = ForgotPasswordToken(
            user_id=user.id,
            token=_new_token(),
            expiry_date=_utcnow()
            + timedelta(minutes=auth_settings.PASSWORD_RESET_EXPIRE_MINUTES),
        )
        self.session.add(token)
        await commit_or_conflict(self.session)
        return ForgotPasswordResponse(
            message="If the account exists, a reset token has been created",
            token=token.token,
        )

    async def reset_password(self, data: ResetPasswordRequest) -> MessageResponse:
        forgot = await self.session.scalar(
            select(ForgotPasswordToken).where(ForgotPasswordToken.token == data.token)
        )
        if forgot is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Reset token is invalid",
            )
        if forgot.expiry_date < _utcnow():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Reset token has expired",
            )
        if forgot.number_of_time >= auth_settings.PASSWORD_RESET_MAX_ATTEMPTS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Reset token has been used too many times",
            )
        user = await get_or_404(self.session, User, forgot.user_id)
        forgot.number_of_time += 1
        user.password = hash_password(data.password)
        self.session.add(
            ResetPasswordToken(
                user_id=user.id,
                token=_new_token(),
                expiry_date=_utcnow(),
                number_of_time=1,
            )
        )
        await self.session.delete(forgot)
        self.session.add(user)
        await commit_or_conflict(self.session)
        return MessageResponse(message="Password updated")

    async def _active_invite(self, token: str) -> UserInvite:
        invite = await self.session.scalar(
            select(UserInvite).where(UserInvite.token == token)
        )
        if invite is None or invite.accepted_at is not None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invite is invalid",
            )
        if invite.expiry_date < _utcnow():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invite has expired",
            )
        return invite
