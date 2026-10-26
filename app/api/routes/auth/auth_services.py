import hashlib
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from uuid import UUID

from fastapi import HTTPException, status
from jose import jwt
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import delete, select

from app.api.routes.auth.auth_model import (
    ForgotPasswordToken,
    RefreshToken,
    ResetPasswordToken,
    UserInvite,
)
from app.api.routes.auth.auth_schemas import (
    ForgotPasswordRequest,
    InviteCreate,
    LoginRequest,
    ResetPasswordRequest,
    SignupRequest,
)
from app.api.routes.auth.rate_limit import (
    FORGOT_RESET,
    RESET_EMAIL,
    RESET_EMAIL_IP,
    ensure_allowed,
    record_attempt,
)
from app.api.routes.attendance.attendance_services import close_attendance, open_attendance
from app.api.routes.user.user_model import Role, User
from app.api.routes.user.user_schemas import UserRead
from app.api.schemas.common import MessageResponse
from app.api.security.cookies import hash_ip, hash_token, new_secret
from app.config import auth_settings
from app.db.repository import commit_or_conflict, get_or_404
from app.utility.email import EmailSendError, send_email

_GENERIC_RESET = "If the account exists, a reset link has been sent"


@dataclass
class IssuedSession:
    access_token: str
    refresh_token: str
    csrf_token: str
    user: UserRead


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


def _access_token(user_id: UUID) -> str:
    expires = _utcnow() + timedelta(minutes=auth_settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    return jwt.encode(
        {"sub": str(user_id), "exp": expires},
        auth_settings.JWT_SECRET,
        algorithm=auth_settings.JWT_ALGORITHM,
    )


async def _user_read(session: AsyncSession, user: User) -> UserRead:
    role = await session.get(Role, user.role_id)
    payload = UserRead.model_validate(user)
    return payload.model_copy(update={"role_name": role.role_name if role else None})


async def revoke_refresh_tokens(session: AsyncSession, user_id: UUID) -> None:
    await session.execute(delete(RefreshToken).where(RefreshToken.user_id == user_id))


class AuthService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create_invite(self, data: InviteCreate, actor: User) -> MessageResponse:
        role = await get_or_404(self.session, Role, data.role_id)
        actor_role = await get_or_404(self.session, Role, actor.role_id)
        from app.api.security.permissions import can_manage_role

        if not can_manage_role(actor_role.role_name, role.role_name):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You cannot invite this role",
            )
        email = data.email.strip().lower()
        existing = await self.session.scalar(select(User).where(User.email == email))
        if existing is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="An account already exists for this email",
            )
        raw_token = new_secret()
        invite = UserInvite(
            email=email,
            first_name=data.first_name.strip(),
            last_name=data.last_name.strip() if data.last_name else None,
            role_id=role.id,
            token_hash=hash_token(raw_token),
            expiry_date=_utcnow() + timedelta(days=auth_settings.INVITE_EXPIRE_DAYS),
            invited_by_user_id=actor.id,
        )
        self.session.add(invite)
        await self.session.flush()
        link = f"{auth_settings.FRONTEND_URL}/accept-invite?token={raw_token}"
        try:
            await send_email(
                email,
                (
                    f"Hello {invite.first_name},\n\n"
                    "You have been invited to the ERP. Set your password here:\n"
                    f"{link}\n\n"
                    "This link expires "
                    f"in {auth_settings.INVITE_EXPIRE_DAYS} days."
                ),
                "You are invited to the ERP",
                html_content=(
                    f"<p>Hello {invite.first_name},</p>"
                    "<p>You have been invited to the ERP. Set your password here:</p>"
                    f'<p><a href="{link}">{link}</a></p>'
                ),
            )
        except EmailSendError as exc:
            await self.session.rollback()
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Invite was not sent because email is unavailable",
            ) from exc
        await commit_or_conflict(self.session)
        return MessageResponse(message="Invite sent")

    async def signup(self, data: SignupRequest, client_ip: str) -> IssuedSession:
        invite = await self._active_invite(data.token)
        existing = await self.session.scalar(select(User).where(User.email == invite.email))
        if existing is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="An account already exists for this invite",
            )
        user = User(
            first_name=invite.first_name,
            last_name=invite.last_name,
            email=invite.email,
            password=hash_password(data.password),
            role_id=invite.role_id,
        )
        invite.accepted_at = _utcnow()
        self.session.add(user)
        self.session.add(invite)
        await self.session.flush()
        return await self._issue_session(user, client_ip)

    async def login(self, data: LoginRequest, client_ip: str) -> IssuedSession:
        email = data.email.strip().lower()
        user = await self.session.scalar(select(User).where(User.email == email))
        if user is None or not verify_password(data.password, user.password):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect email or password",
            )
        await ensure_allowed(
            self.session,
            action=FORGOT_RESET,
            user_id=user.id,
            daily=True,
            message="This account is locked after too many password resets",
        )
        return await self._issue_session(user, client_ip)

    async def refresh(self, raw_token: str, client_ip: str) -> IssuedSession:
        presented_hash = hash_token(raw_token)
        row = await self.session.scalar(
            select(RefreshToken).where(RefreshToken.token_hash == presented_hash)
        )
        if row is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Refresh token is invalid",
            )
        if row.client_ip_hash != hash_ip(client_ip):
            await self.session.delete(row)
            await commit_or_conflict(self.session)
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Session ended because the network address changed",
            )
        if row.rotated_at is not None:
            return await self._refresh_rotated(row)
        if row.expiry_date < _utcnow():
            await self.session.delete(row)
            await commit_or_conflict(self.session)
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Refresh token has expired",
            )
        user = await get_or_404(self.session, User, row.user_id)
        new_raw = new_secret()
        new_hash = hash_token(new_raw)
        row.rotated_at = _utcnow()
        row.replaced_by_hash = new_hash
        row.successor_token = new_raw
        self.session.add(
            RefreshToken(
                user_id=user.id,
                token_hash=new_hash,
                client_ip_hash=row.client_ip_hash,
                expiry_date=_utcnow()
                + timedelta(days=auth_settings.REFRESH_TOKEN_EXPIRE_DAYS),
            )
        )
        self.session.add(row)
        await commit_or_conflict(self.session)
        return IssuedSession(
            access_token=_access_token(user.id),
            refresh_token=new_raw,
            csrf_token=new_secret(),
            user=await _user_read(self.session, user),
        )

    async def logout(self, raw_token: str | None) -> None:
        if not raw_token:
            return
        row = await self.session.scalar(
            select(RefreshToken).where(RefreshToken.token_hash == hash_token(raw_token))
        )
        if row is None:
            return
        user = await self.session.get(User, row.user_id)
        if user is not None:
            await close_attendance(self.session, user)
        await self.session.delete(row)
        await commit_or_conflict(self.session)

    async def forgot_password(self, data: ForgotPasswordRequest, client_ip: str) -> MessageResponse:
        await self._send_reset(data.email, client_ip)
        return MessageResponse(message=_GENERIC_RESET)

    async def resend_reset(self, data: ForgotPasswordRequest, client_ip: str) -> MessageResponse:
        await self._send_reset(data.email, client_ip)
        return MessageResponse(message=_GENERIC_RESET)

    async def reset_password(self, data: ResetPasswordRequest) -> MessageResponse:
        forgot = await self.session.scalar(
            select(ForgotPasswordToken).where(
                ForgotPasswordToken.token_hash == hash_token(data.token)
            )
        )
        if forgot is None or forgot.expiry_date < _utcnow():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Reset link is invalid or expired",
            )
        await ensure_allowed(
            self.session,
            action=FORGOT_RESET,
            user_id=forgot.user_id,
            daily=True,
            message="Password reset is locked for this account",
        )
        user = await get_or_404(self.session, User, forgot.user_id)
        user.password = hash_password(data.password)
        forgot.number_of_time += 1
        self.session.add(
            ResetPasswordToken(
                user_id=user.id,
                token_hash=hash_token(new_secret()),
                expiry_date=_utcnow(),
                number_of_time=1,
            )
        )
        await self.session.delete(forgot)
        await revoke_refresh_tokens(self.session, user.id)
        self.session.add(user)
        await record_attempt(
            self.session,
            action=FORGOT_RESET,
            user_id=user.id,
            max_count=auth_settings.FORGOT_PASSWORD_MAX_PER_DAY,
            lock_hours=auth_settings.FORGOT_PASSWORD_LOCK_HOURS,
            daily=True,
        )
        await commit_or_conflict(self.session)
        return MessageResponse(message="Password updated")

    async def _send_reset(self, email: str, client_ip: str) -> None:
        ip_hash = hash_ip(client_ip)
        await ensure_allowed(
            self.session,
            action=RESET_EMAIL_IP,
            client_ip_hash=ip_hash,
            message="Reset email is temporarily blocked",
        )
        normalized = email.strip().lower()
        user = await self.session.scalar(select(User).where(User.email == normalized))
        if user is None:
            await record_attempt(
                self.session,
                action=RESET_EMAIL_IP,
                client_ip_hash=ip_hash,
                max_count=auth_settings.RESET_EMAIL_MAX_SENDS,
                lock_hours=auth_settings.RESET_EMAIL_BLOCK_HOURS,
            )
            await commit_or_conflict(self.session)
            return
        await ensure_allowed(
            self.session,
            action=RESET_EMAIL,
            user_id=user.id,
            message="Reset email is temporarily blocked",
        )
        await ensure_allowed(
            self.session,
            action=FORGOT_RESET,
            user_id=user.id,
            daily=True,
            message="Password reset is locked for this account",
        )
        raw_token = new_secret()
        self.session.add(
            ForgotPasswordToken(
                user_id=user.id,
                token_hash=hash_token(raw_token),
                expiry_date=_utcnow()
                + timedelta(minutes=auth_settings.PASSWORD_RESET_EXPIRE_MINUTES),
            )
        )
        await self.session.flush()
        link = f"{auth_settings.FRONTEND_URL}/reset-password?token={raw_token}"
        try:
            await send_email(
                user.email,
                (
                    "Reset your ERP password:\n"
                    f"{link}\n\n"
                    "This link expires in "
                    f"{auth_settings.PASSWORD_RESET_EXPIRE_MINUTES} minutes."
                ),
                "Reset your ERP password",
                html_content=(
                    "<p>Reset your ERP password:</p>"
                    f'<p><a href="{link}">{link}</a></p>'
                ),
            )
        except EmailSendError as exc:
            await self.session.rollback()
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Reset email could not be sent",
            ) from exc
        await record_attempt(
            self.session,
            action=RESET_EMAIL,
            user_id=user.id,
            max_count=auth_settings.RESET_EMAIL_MAX_SENDS,
            lock_hours=auth_settings.RESET_EMAIL_BLOCK_HOURS,
        )
        await record_attempt(
            self.session,
            action=RESET_EMAIL_IP,
            client_ip_hash=ip_hash,
            max_count=auth_settings.RESET_EMAIL_MAX_SENDS,
            lock_hours=auth_settings.RESET_EMAIL_BLOCK_HOURS,
        )
        await commit_or_conflict(self.session)

    async def _issue_session(self, user: User, client_ip: str) -> IssuedSession:
        raw = new_secret()
        self.session.add(
            RefreshToken(
                user_id=user.id,
                token_hash=hash_token(raw),
                client_ip_hash=hash_ip(client_ip),
                expiry_date=_utcnow()
                + timedelta(days=auth_settings.REFRESH_TOKEN_EXPIRE_DAYS),
            )
        )
        await open_attendance(self.session, user)
        await commit_or_conflict(self.session)
        return IssuedSession(
            access_token=_access_token(user.id),
            refresh_token=raw,
            csrf_token=new_secret(),
            user=await _user_read(self.session, user),
        )

    async def _refresh_rotated(self, row: RefreshToken) -> IssuedSession:
        grace = timedelta(seconds=auth_settings.REFRESH_REUSE_GRACE_SECONDS)
        within_grace = (
            row.successor_token is not None
            and row.replaced_by_hash is not None
            and row.rotated_at is not None
            and row.rotated_at + grace >= _utcnow()
        )
        if within_grace:
            successor = await self.session.scalar(
                select(RefreshToken).where(RefreshToken.token_hash == row.replaced_by_hash)
            )
            if successor is not None and successor.rotated_at is None:
                user = await get_or_404(self.session, User, successor.user_id)
                return IssuedSession(
                    access_token=_access_token(user.id),
                    refresh_token=row.successor_token or "",
                    csrf_token=new_secret(),
                    user=await _user_read(self.session, user),
                )
        await revoke_refresh_tokens(self.session, row.user_id)
        await commit_or_conflict(self.session)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session ended because the refresh token was reused",
        )

    async def _active_invite(self, token: str) -> UserInvite:
        invite = await self.session.scalar(
            select(UserInvite).where(UserInvite.token_hash == hash_token(token))
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
