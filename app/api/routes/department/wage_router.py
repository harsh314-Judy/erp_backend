from datetime import datetime
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Query

from app.api.db_dependency import PGSessionDep
from app.api.dependencies import CurrentUserDep
from app.api.routes.department.wage_schemas import AdvanceWrite, DayMark, WageMonth, WageOwed
from app.api.routes.department.wage_services import WageService
from app.api.routes.user.user_model import Role
from app.api.security.permissions import MANAGE_STAFF_USERS, VIEW_FINANCIALS, VIEW_REPORTS, forbid, role_has

router = APIRouter(tags=["wages"])


async def _role(session: PGSessionDep, user: CurrentUserDep) -> str:
    role = await session.get(Role, user.role_id)
    return role.role_name if role else ""


def _sees_wages(name: str) -> bool:
    return role_has(name, MANAGE_STAFF_USERS) or role_has(name, VIEW_FINANCIALS)


@router.get("/wages", response_model=WageMonth)
async def wage_month(
    session: PGSessionDep,
    user: CurrentUserDep,
    year: int = Query(ge=2000, le=2100),
    month: int = Query(ge=1, le=12),
) -> WageMonth:
    if not _sees_wages(await _role(session, user)):
        forbid()
    return await WageService(session).month(year, month)


@router.put("/wages/days", response_model=WageMonth)
async def mark_floor_day(
    data: DayMark,
    session: PGSessionDep,
    user: CurrentUserDep,
) -> WageMonth:
    if not _sees_wages(await _role(session, user)):
        forbid()
    return await WageService(session).mark_day(data)


@router.put("/wages/advances", response_model=WageMonth)
async def set_already_given(
    data: AdvanceWrite,
    session: PGSessionDep,
    user: CurrentUserDep,
) -> WageMonth:
    if not _sees_wages(await _role(session, user)):
        forbid()
    return await WageService(session).set_advance(data)


@router.get("/reports/wages", response_model=WageOwed)
async def wage_owed_this_month(session: PGSessionDep, user: CurrentUserDep) -> WageOwed:
    name = await _role(session, user)
    if not role_has(name, VIEW_REPORTS) or not _sees_wages(name):
        forbid()
    today = datetime.now(ZoneInfo("Asia/Kolkata")).date()
    month = await WageService(session).month(today.year, today.month)
    return WageOwed(year=month.year, month=month.month, total_owed=month.total_owed)
