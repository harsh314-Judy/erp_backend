from datetime import datetime

from fastapi import APIRouter, Query

from app.api.db_dependency import PGSessionDep
from app.api.dependencies import CurrentUserDep
from app.api.routes.activity.activity_schemas import ActivityRead
from app.api.routes.activity.activity_services import list_activity, present_activity
from app.api.routes.user.user_model import Role
from app.api.security.permissions import VIEW_REPORTS, forbid, role_has

router = APIRouter(prefix="/activity", tags=["activity"])


@router.get("", response_model=list[ActivityRead])
async def activity_log(
    session: PGSessionDep,
    user: CurrentUserDep,
    start: datetime = Query(alias="from"),
    end: datetime = Query(alias="to"),
    kind: str | None = None,
) -> list[ActivityRead]:
    role = await session.get(Role, user.role_id)
    if not role_has(role.role_name if role else None, VIEW_REPORTS):
        forbid()
    rows = await list_activity(session, start=start, end=end, kind=kind or None)
    role_name = role.role_name if role else None
    return await present_activity(session, rows, hide_figures=role_name in {"accountant", "staff"})
