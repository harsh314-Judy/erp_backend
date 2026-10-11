import asyncio
import logging
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from sqlalchemy import and_, or_
from sqlalchemy.ext.asyncio import async_sessionmaker
from sqlmodel import delete

from app.api.routes.auth.auth_model import RefreshToken
from app.config import auth_settings

logger = logging.getLogger(__name__)


async def purge_expired_refresh_tokens(sessionmaker: async_sessionmaker) -> None:
    now = datetime.now(timezone.utc)
    grace = timedelta(seconds=auth_settings.REFRESH_REUSE_GRACE_SECONDS)
    async with sessionmaker() as session:
        await session.execute(
            delete(RefreshToken).where(
                or_(
                    RefreshToken.expiry_date < now,
                    and_(
                        RefreshToken.rotated_at.is_not(None),
                        RefreshToken.rotated_at < now - grace,
                    ),
                )
            )
        )
        await session.commit()


async def refresh_cleanup_loop(sessionmaker: async_sessionmaker) -> None:
    await purge_expired_refresh_tokens(sessionmaker)
    tz = ZoneInfo(auth_settings.APP_TIMEZONE)
    while True:
        now = datetime.now(tz)
        tomorrow = (now + timedelta(days=1)).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        await asyncio.sleep((tomorrow - now).total_seconds())
        try:
            await purge_expired_refresh_tokens(sessionmaker)
        except Exception:
            logger.exception("refresh token cleanup failed")
