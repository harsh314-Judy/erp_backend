from fastapi import APIRouter, Query, Request
from fastapi.responses import Response

from app.api.dependencies import AdminUserDep, CurrentUserDep, PGSessionDep
from uuid import UUID

from app.api.routes.activity.activity_schemas import (
    ActivityBoard,
    BreakAllowanceUpdate,
    BreakRosterItem,
    BreakUpdate,
    PresenceRead,
    VisitCreate,
)
from app.api.routes.activity.activity_services import (
    board,
    break_roster,
    export_rows,
    own_presence,
    record_visit,
    set_break,
    set_break_allowance,
)
from app.api.routes.activity.device import DeviceHint
from app.api.routes.activity.xlsx import workbook
from app.api.security.client_ip import client_ip

router = APIRouter(prefix="/activity", tags=["activity"])


def _header(request: Request, name: str) -> str | None:
    value = request.headers.get(name)
    if value is None:
        return None
    return value.strip().strip('"') or None


def hint_from(request: Request) -> DeviceHint:
    mobile = request.headers.get("sec-ch-ua-mobile")
    return DeviceHint(
        user_agent=request.headers.get("user-agent"),
        model=_header(request, "sec-ch-ua-model"),
        platform=_header(request, "sec-ch-ua-platform"),
        mobile=True if mobile == "?1" else False if mobile == "?0" else None,
    )


@router.get("/me", response_model=PresenceRead)
async def my_presence(session: PGSessionDep, user: CurrentUserDep) -> PresenceRead:
    return await own_presence(session, user)


@router.post("/visit", response_model=PresenceRead)
async def visit(
    data: VisitCreate,
    request: Request,
    session: PGSessionDep,
    user: CurrentUserDep,
) -> PresenceRead:
    await record_visit(session, user, data.module, hint_from(request), client_ip(request))
    return await own_presence(session, user)


@router.post("/break", response_model=PresenceRead)
async def update_break(
    data: BreakUpdate,
    request: Request,
    session: PGSessionDep,
    user: CurrentUserDep,
) -> PresenceRead:
    return await set_break(session, user, data.on_break)


@router.get("/breaks", response_model=list[BreakRosterItem])
async def list_breaks(session: PGSessionDep, _: AdminUserDep) -> list[BreakRosterItem]:
    return await break_roster(session)


@router.patch("/breaks/{user_id}", response_model=BreakRosterItem)
async def update_break_allowance(
    user_id: UUID,
    data: BreakAllowanceUpdate,
    session: PGSessionDep,
    _: AdminUserDep,
) -> BreakRosterItem:
    return await set_break_allowance(session, user_id, data.minutes)


@router.get("/board", response_model=ActivityBoard)
async def activity_board(
    session: PGSessionDep,
    _: AdminUserDep,
    role: str = Query(min_length=1, max_length=32),
) -> ActivityBoard:
    return await board(session, role)


@router.get("/export")
async def export_activity(
    session: PGSessionDep,
    _: AdminUserDep,
    role: str | None = Query(default=None, max_length=32),
) -> Response:
    rows = await export_rows(session, role)
    name = f"activity-{role or 'all'}.xlsx"
    return Response(
        content=workbook(rows),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{name}"'},
    )
