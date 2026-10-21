from datetime import datetime, timedelta
from uuid import UUID
from zoneinfo import ZoneInfo

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import col, select

from app.api.routes.activity.activity_model import ActivityLog, StaffPresence
from app.api.routes.activity.activity_schemas import (
    ActivityBoard,
    ActivityEvent,
    BreakRosterItem,
    PersonStatus,
    PresenceRead,
)
from app.api.routes.activity.device import DeviceFacts, DeviceHint, facts_from
from app.api.routes.user.user_model import Role, User
from app.db.base import utcnow
from app.db.repository import commit_or_conflict, get_or_404

PLANT_ZONE = ZoneInfo("Asia/Kolkata")
BREAK_CHOICES = frozenset({30, 45, 60})
_VISIT_GAP = timedelta(minutes=15)
_BOARD_LIMIT = 40
_EXPORT_LIMIT = 20000


def person_name(user: User) -> str:
    return " ".join(part for part in (user.first_name, user.last_name) if part)


async def write_activity(
    session: AsyncSession,
    user: User,
    action: str,
    summary: str,
    hint: DeviceHint | None = None,
    ip: str | None = None,
    *,
    touch_login: bool = False,
    update_presence: bool = True,
) -> None:
    """Add one log row and refresh the live presence row. The caller commits."""
    role = await session.get(Role, user.role_id)
    facts = _facts_or_none(hint)
    now = utcnow()
    session.add(
        ActivityLog(
            user_id=user.id,
            person=person_name(user)[:160],
            role_name=(role.role_name if role else "member")[:32],
            action=action[:32],
            summary=summary[:160],
            ip=ip[:45] if ip else None,
            browser=None if facts is None else facts.browser,
            os_name=None if facts is None else facts.os_name,
            device_type=None if facts is None else facts.device_type,
            device_model=None if facts is None else facts.device_model,
        )
    )
    if update_presence:
        await _touch_presence(
            session,
            user.id,
            facts,
            now,
            touch_login=touch_login,
        )


async def record_visit(session: AsyncSession, user: User, module: str, hint: DeviceHint, ip: str) -> None:
    label = " ".join(module.split())[:40] or "App"
    latest = await session.scalar(
        select(ActivityLog)
        .where(ActivityLog.user_id == user.id, ActivityLog.action == "visit", ActivityLog.summary == label)
        .order_by(col(ActivityLog.created_at).desc())
        .limit(1)
    )
    now = utcnow()
    if latest is not None and latest.created_at >= now - _VISIT_GAP:
        await _touch_presence(session, user.id, facts_from(hint), now)
        await commit_or_conflict(session)
        return
    await write_activity(session, user, "visit", label, hint, ip)
    await commit_or_conflict(session)


async def set_break(session: AsyncSession, user: User, on_break: bool) -> PresenceRead:
    """Start or pause the person's own timer. This is not written to the activity log."""
    if user.daily_break_minutes not in BREAK_CHOICES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No break time is allocated for this account",
        )
    allowance = user.daily_break_minutes * 60
    now = utcnow()
    row = await session.get(StaffPresence, user.id)
    if row is None:
        row = StaffPresence(user_id=user.id)
    _roll_break_day(row)
    _stop_if_allowance_spent(row, allowance, now)
    if on_break:
        if not row.on_break:
            if row.break_used_seconds >= allowance:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Today's break time is used up",
                )
            row.on_break = True
            row.break_started_at = now
    elif row.on_break and row.break_started_at is not None:
        elapsed = max(0, int((now - row.break_started_at).total_seconds()))
        row.break_used_seconds = min(allowance, row.break_used_seconds + elapsed)
        row.on_break = False
        row.break_started_at = None
    else:
        row.on_break = False
        row.break_started_at = None
    session.add(row)
    await commit_or_conflict(session)
    return _presence_read(row, user)


async def own_presence(session: AsyncSession, user: User) -> PresenceRead:
    row = await session.get(StaffPresence, user.id)
    if row is None:
        return _presence_read(None, user)
    before = (row.on_break, row.break_used_seconds, row.break_day, row.break_started_at)
    _roll_break_day(row)
    if user.daily_break_minutes in BREAK_CHOICES:
        _stop_if_allowance_spent(row, user.daily_break_minutes * 60, utcnow())
    after = (row.on_break, row.break_used_seconds, row.break_day, row.break_started_at)
    if after != before:
        session.add(row)
        await commit_or_conflict(session)
    return _presence_read(row, user)


async def pause_running_break(session: AsyncSession, user: User) -> None:
    """Keep the unused minutes when a new sign-in interrupts a running timer."""
    row = await session.get(StaffPresence, user.id)
    if row is None or not row.on_break:
        return
    _roll_break_day(row)
    allowance = (user.daily_break_minutes or 0) * 60
    if row.on_break and row.break_started_at is not None and allowance:
        elapsed = max(0, int((utcnow() - row.break_started_at).total_seconds()))
        row.break_used_seconds = min(allowance, row.break_used_seconds + elapsed)
    row.on_break = False
    row.break_started_at = None
    session.add(row)


async def break_roster(session: AsyncSession) -> list[BreakRosterItem]:
    rows = (
        await session.execute(
            select(User, Role).join(Role, Role.id == User.role_id).order_by(User.first_name, User.last_name)
        )
    ).all()
    return [_roster_item(user, role.role_name) for user, role in rows]


async def set_break_allowance(session: AsyncSession, user_id: UUID, minutes: int | None) -> BreakRosterItem:
    if minutes not in BREAK_CHOICES and minutes is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Break time must be 30, 45, or 60 minutes",
        )
    user = await get_or_404(session, User, user_id)
    user.daily_break_minutes = minutes
    session.add(user)
    await commit_or_conflict(session)
    role = await session.get(Role, user.role_id)
    return _roster_item(user, role.role_name if role else None)


async def board(session: AsyncSession, role_name: str) -> ActivityBoard:
    today = _day_start()
    people_rows = (
        await session.execute(
            select(StaffPresence, User, Role)
            .join(User, User.id == StaffPresence.user_id)
            .join(Role, Role.id == User.role_id)
            .where(Role.role_name == role_name)
        )
    ).all()
    people = [
        PersonStatus(user_id=user.id, **_presence_read(presence, user).model_dump())
        for presence, user, _role in people_rows
    ]
    event_rows = (
        await session.execute(
            select(ActivityLog)
            .where(ActivityLog.role_name == role_name, ActivityLog.created_at >= _year_start())
            .order_by(col(ActivityLog.created_at).desc())
            .limit(_BOARD_LIMIT)
        )
    ).scalars().all()
    return ActivityBoard(
        seen_today=sum(1 for person in people if person.last_seen_at is not None and person.last_seen_at >= today),
        people=people,
        events=[_event(row) for row in event_rows],
    )


async def export_rows(session: AsyncSession, role_name: str | None) -> list[list[str]]:
    statement = select(ActivityLog).where(ActivityLog.created_at >= _year_start())
    if role_name:
        statement = statement.where(ActivityLog.role_name == role_name)
    rows = (
        await session.execute(
            statement.order_by(col(ActivityLog.created_at).desc()).limit(_EXPORT_LIMIT)
        )
    ).scalars().all()
    header = [
        "When (India)",
        "Person",
        "Role",
        "Action",
        "Detail",
        "Browser",
        "Operating system",
        "Device type",
        "Model",
        "IP address",
    ]
    table = [header]
    for row in rows:
        when = row.created_at.astimezone(PLANT_ZONE).strftime("%Y-%m-%d %H:%M")
        table.append(
            [
                when,
                row.person,
                row.role_name,
                row.action,
                row.summary,
                row.browser or "",
                row.os_name or "",
                row.device_type or "",
                row.device_model or "",
                row.ip or "",
            ]
        )
    return table


async def _touch_presence(
    session: AsyncSession,
    user_id: UUID,
    facts: DeviceFacts | None,
    now: datetime,
    *,
    touch_login: bool = False,
) -> None:
    row = await session.get(StaffPresence, user_id)
    if row is None:
        row = StaffPresence(user_id=user_id)
    row.last_seen_at = now
    if facts is not None:
        row.device_label = facts.label
    if touch_login:
        row.last_login_at = now
    session.add(row)


def _roll_break_day(row: StaffPresence) -> None:
    today = datetime.now(PLANT_ZONE).date()
    if row.break_day == today:
        return
    row.break_day = today
    row.break_used_seconds = 0
    row.on_break = False
    row.break_started_at = None


def _stop_if_allowance_spent(row: StaffPresence, allowance_seconds: int, now: datetime) -> None:
    if not row.on_break or row.break_started_at is None:
        return
    elapsed = max(0, int((now - row.break_started_at).total_seconds()))
    if row.break_used_seconds + elapsed >= allowance_seconds:
        row.break_used_seconds = allowance_seconds
        row.on_break = False
        row.break_started_at = None


def _presence_read(row: StaffPresence | None, user: User) -> PresenceRead:
    return PresenceRead(
        on_break=False if row is None else row.on_break,
        break_started_at=None if row is None else row.break_started_at,
        last_login_at=None if row is None else row.last_login_at,
        last_seen_at=None if row is None else row.last_seen_at,
        device_label=None if row is None else row.device_label,
        break_allowance_minutes=user.daily_break_minutes,
        break_used_seconds=0 if row is None else row.break_used_seconds,
    )


def _roster_item(user: User, role_name: str | None) -> BreakRosterItem:
    return BreakRosterItem(
        user_id=user.id,
        person=person_name(user),
        role_name=role_name,
        email=user.email,
        minutes=user.daily_break_minutes,
    )


def _event(row: ActivityLog) -> ActivityEvent:
    return ActivityEvent(
        id=row.id,
        user_id=row.user_id,
        person=row.person,
        role_name=row.role_name,
        action=row.action,
        summary=row.summary,
        browser=row.browser,
        os_name=row.os_name,
        device_type=row.device_type,
        device_model=row.device_model,
        created_at=row.created_at,
    )


def _facts_or_none(hint: DeviceHint | None) -> DeviceFacts | None:
    if hint is None or not (hint.user_agent or hint.platform or hint.model):
        return None
    return facts_from(hint)


def _year_start() -> datetime:
    now = datetime.now(PLANT_ZONE)
    return datetime(now.year, 1, 1, tzinfo=PLANT_ZONE)


def _day_start() -> datetime:
    now = datetime.now(PLANT_ZONE)
    return datetime(now.year, now.month, now.day, tzinfo=PLANT_ZONE)
