from uuid import UUID

from fastapi import APIRouter
from sqlmodel import select

from app.api.db_dependency import PGSessionDep
from app.api.dependencies import CurrentUserDep
from app.api.routes.notification.notification_model import Notification
from app.api.routes.notification.notification_schemas import NotificationRead
from app.api.routes.notification.notification_services import mark_read, unread_count

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("", response_model=list[NotificationRead])
async def list_notifications(
    session: PGSessionDep, user: CurrentUserDep
) -> list[Notification]:
    result = await session.scalars(
        select(Notification)
        .where(Notification.user_id == user.id)
        .order_by(Notification.created_at.desc())
        .limit(30)
    )
    return list(result)


@router.get("/unread-count")
async def count_unread(session: PGSessionDep, user: CurrentUserDep) -> dict[str, int]:
    return {"count": await unread_count(session, user.id)}


@router.post("/{notification_id}/read", response_model=NotificationRead)
async def read_notification(
    notification_id: UUID, session: PGSessionDep, user: CurrentUserDep
) -> Notification:
    row = await mark_read(session, user.id, notification_id)
    if row is None:
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail="Notification not found")
    return row
