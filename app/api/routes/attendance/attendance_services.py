from datetime import datetime
from zoneinfo import ZoneInfo

from sqlalchemy import or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.api.routes.attendance.attendance_model import Attendance
from app.api.routes.attendance.attendance_schemas import AttendanceRead
from app.api.routes.user.user_model import Role, User
from app.db.base import utcnow

PLANT_ZONE = ZoneInfo("Asia/Kolkata")


def _person(user: User) -> str:
    return " ".join(part for part in (user.first_name, user.last_name) if part)[:160]


async def open_attendance(session: AsyncSession, user: User) -> None:
    """Close any open session, then record this sign-in. The caller commits."""
    now = utcnow()
    open_rows = (
        await session.execute(
            select(Attendance).where(Attendance.user_id == user.id, Attendance.signed_out_at.is_(None))
        )
    ).scalars().all()
    for row in open_rows:
        row.signed_out_at = now
        session.add(row)
    role = await session.get(Role, user.role_id)
    session.add(
        Attendance(
            user_id=user.id,
            person=_person(user),
            role_name=(role.role_name if role else "member")[:32],
            signed_in_at=now,
        )
    )


async def close_attendance(session: AsyncSession, user: User) -> None:
    """Fill the sign-out time on every open session for this person. The caller commits."""
    now = utcnow()
    rows = (
        await session.execute(
            select(Attendance).where(Attendance.user_id == user.id, Attendance.signed_out_at.is_(None))
        )
    ).scalars().all()
    for row in rows:
        row.signed_out_at = now
        session.add(row)


async def month_attendance(session: AsyncSession, year: int, month: int) -> list[AttendanceRead]:
    start = datetime(year, month, 1, tzinfo=PLANT_ZONE)
    end = datetime(year + 1, 1, 1, tzinfo=PLANT_ZONE) if month == 12 else datetime(year, month + 1, 1, tzinfo=PLANT_ZONE)
    rows = (
        await session.execute(
            select(Attendance)
            .where(
                Attendance.signed_in_at < end,
                or_(Attendance.signed_out_at.is_(None), Attendance.signed_out_at >= start),
            )
            .order_by(Attendance.signed_in_at)
        )
    ).scalars().all()
    return [
        AttendanceRead(
            id=row.id,
            person=row.person,
            role_name=row.role_name,
            signed_in_at=row.signed_in_at,
            signed_out_at=row.signed_out_at,
        )
        for row in rows
    ]
