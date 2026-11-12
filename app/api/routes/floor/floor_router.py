from datetime import date
from uuid import UUID

from fastapi import APIRouter, Query, Response, status

from app.api.db_dependency import PGSessionDep
from app.api.dependencies import CurrentUserDep, FloorServiceDep
from app.api.routes.floor.floor_schemas import FloorEntryRead, FloorEntryWrite, FloorSummary, WorkerTimeline
from app.api.routes.user.user_model import Role
from app.api.schemas.pagination import PaginatedResponse, PaginationDep
from app.api.security.permissions import EDIT_INVENTORY, VIEW_ASSIGNED_WORK, forbid, role_has

router = APIRouter(prefix="/floor", tags=["floor"])


async def _role(session: PGSessionDep, user: CurrentUserDep) -> str:
    role = await session.get(Role, user.role_id)
    return role.role_name if role else ""


def _can_read(name: str) -> None:
    if not role_has(name, VIEW_ASSIGNED_WORK):
        forbid()


def _can_write(name: str) -> None:
    if not (role_has(name, VIEW_ASSIGNED_WORK) or role_has(name, EDIT_INVENTORY)):
        forbid()


@router.get("/summary", response_model=FloorSummary)
async def floor_summary(
    service: FloorServiceDep,
    session: PGSessionDep,
    user: CurrentUserDep,
    date_from: date | None = None,
    date_to: date | None = None,
) -> FloorSummary:
    _can_read(await _role(session, user))
    return await service.summary(date_from, date_to)


@router.get("/entries", response_model=PaginatedResponse[FloorEntryRead])
async def list_entries(
    service: FloorServiceDep,
    pagination: PaginationDep,
    session: PGSessionDep,
    user: CurrentUserDep,
    operation_id: UUID | None = None,
    worker_id: UUID | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
) -> PaginatedResponse[FloorEntryRead]:
    _can_read(await _role(session, user))
    return await service.list_entries(
        pagination,
        operation_id=operation_id,
        worker_id=worker_id,
        date_from=date_from,
        date_to=date_to,
    )


@router.post("/entries", response_model=FloorEntryRead, status_code=status.HTTP_201_CREATED)
async def create_entry(
    data: FloorEntryWrite,
    service: FloorServiceDep,
    session: PGSessionDep,
    user: CurrentUserDep,
) -> FloorEntryRead:
    _can_write(await _role(session, user))
    return await service.create_entry(data, user)


@router.patch("/entries/{entry_id}", response_model=FloorEntryRead)
async def update_entry(
    entry_id: UUID,
    data: FloorEntryWrite,
    service: FloorServiceDep,
    session: PGSessionDep,
    user: CurrentUserDep,
) -> FloorEntryRead:
    name = await _role(session, user)
    _can_write(name)
    return await service.update_entry(entry_id, data, user, can_edit_others=role_has(name, EDIT_INVENTORY))


@router.delete("/entries/{entry_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_entry(
    entry_id: UUID,
    service: FloorServiceDep,
    session: PGSessionDep,
    user: CurrentUserDep,
) -> Response:
    name = await _role(session, user)
    _can_write(name)
    await service.delete_entry(entry_id, user, can_edit_others=role_has(name, EDIT_INVENTORY))
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/workers/{worker_id}/timeline", response_model=WorkerTimeline)
async def worker_timeline(
    worker_id: UUID,
    service: FloorServiceDep,
    session: PGSessionDep,
    user: CurrentUserDep,
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
) -> WorkerTimeline:
    name = await _role(session, user)
    _can_read(name)
    return await service.timeline(worker_id, date_from, date_to, reveal_contact=role_has(name, EDIT_INVENTORY))
