from fastapi import APIRouter, Query

from app.api.dependencies import AdminUserDep, PGSessionDep
from app.api.routes.attendance.attendance_schemas import AttendanceRead
from app.api.routes.attendance.attendance_services import month_attendance

router = APIRouter(prefix="/attendance", tags=["attendance"])


@router.get("", response_model=list[AttendanceRead])
async def list_attendance(
    session: PGSessionDep,
    _: AdminUserDep,
    year: int = Query(ge=2000, le=2100),
    month: int = Query(ge=1, le=12),
) -> list[AttendanceRead]:
    return await month_attendance(session, year, month)
