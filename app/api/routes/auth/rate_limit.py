from datetime import datetime, timedelta, timezone
from uuid import UUID
from zoneinfo import ZoneInfo

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.api.routes.auth.auth_model import AuthRateLimit
from app.config import auth_settings

FORGOT_RESET = "forgot_reset"
RESET_EMAIL = "reset_email"
RESET_EMAIL_IP = "reset_email_ip"
PROFILE_PASSWORD = "profile_password"


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _today_start() -> datetime:
    tz = ZoneInfo(auth_settings.APP_TIMEZONE)
    now = datetime.now(tz)
    start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    return start.astimezone(timezone.utc)


def _lock_detail(locked_until: datetime, message: str) -> dict[str, str]:
    return {"message": message, "locked_until": locked_until.isoformat()}


async def _row(
    session: AsyncSession,
    *,
    action: str,
    user_id: UUID | None = None,
    client_ip_hash: str | None = None,
) -> AuthRateLimit | None:
    statement = select(AuthRateLimit).where(AuthRateLimit.action == action)
    if user_id is not None:
        statement = statement.where(AuthRateLimit.user_id == user_id)
    else:
        statement = statement.where(AuthRateLimit.client_ip_hash == client_ip_hash)
    return await session.scalar(statement)


def _reset_if_stale(row: AuthRateLimit, *, daily: bool) -> None:
    now = _utcnow()
    if row.locked_until and row.locked_until <= now:
        row.count = 0
        row.locked_until = None
        row.window_start = now
        return
    if daily and row.window_start < _today_start() and row.locked_until is None:
        row.count = 0
        row.window_start = now


async def ensure_allowed(
    session: AsyncSession,
    *,
    action: str,
    user_id: UUID | None = None,
    client_ip_hash: str | None = None,
    daily: bool = False,
    message: str,
) -> None:
    row = await _row(
        session, action=action, user_id=user_id, client_ip_hash=client_ip_hash
    )
    if row is None:
        return
    _reset_if_stale(row, daily=daily)
    if row.locked_until and row.locked_until > _utcnow():
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=_lock_detail(row.locked_until, message),
        )


async def record_attempt(
    session: AsyncSession,
    *,
    action: str,
    max_count: int,
    lock_hours: int,
    user_id: UUID | None = None,
    client_ip_hash: str | None = None,
    daily: bool = False,
) -> None:
    now = _utcnow()
    row = await _row(
        session, action=action, user_id=user_id, client_ip_hash=client_ip_hash
    )
    if row is None:
        row = AuthRateLimit(
            user_id=user_id,
            client_ip_hash=client_ip_hash,
            action=action,
            window_start=now,
            count=0,
        )
        session.add(row)
    else:
        _reset_if_stale(row, daily=daily)
    row.count += 1
    if row.count >= max_count:
        row.locked_until = now + timedelta(hours=lock_hours)
    session.add(row)
