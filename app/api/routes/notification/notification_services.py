import logging
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.api.routes.notification.notification_model import Notification
from app.api.routes.user.user_model import User
from app.config import email_settings
from app.utility.email import send_email

logger = logging.getLogger(__name__)


async def user_ids_with(
    session: AsyncSession, capability: str, exclude: UUID | None = None
) -> list[UUID]:
    from app.api.routes.user.user_model import Role
    from app.api.security.permissions import role_has

    rows = await session.execute(select(User.id, Role.role_name).join(Role, Role.id == User.role_id))
    found: list[UUID] = []
    for user_id, role_name in rows:
        if exclude is not None and user_id == exclude:
            continue
        if role_has(role_name, capability):
            found.append(user_id)
    return found


async def notify(
    session: AsyncSession,
    user_ids: list[UUID],
    *,
    title: str,
    body: str,
    kind: str,
    link: str | None = None,
    email: bool = True,
) -> None:
    unique_ids = list(dict.fromkeys(user_ids))
    if not unique_ids:
        return
    for user_id in unique_ids:
        session.add(
            Notification(user_id=user_id, title=title, body=body, kind=kind, link=link)
        )
    await session.flush()
    if not email or not email_settings.is_configured:
        return
    result = await session.scalars(select(User).where(User.id.in_(unique_ids)))  # type: ignore[attr-defined]
    recipients = [user.email for user in result if user.email]
    if not recipients:
        return
    try:
        await send_email(recipients, body, title)
    except Exception:
        logger.exception("notification email failed for %s", title)


async def unread_count(session: AsyncSession, user_id: UUID) -> int:
    result = await session.scalars(
        select(Notification).where(
            Notification.user_id == user_id, Notification.read_at.is_(None)  # type: ignore[union-attr]
        )
    )
    return len(list(result))


async def mark_read(session: AsyncSession, user_id: UUID, notification_id: UUID) -> Notification | None:
    row = await session.get(Notification, notification_id)
    if row is None or row.user_id != user_id:
        return None
    row.read_at = datetime.now(timezone.utc)
    session.add(row)
    await session.commit()
    await session.refresh(row)
    return row
