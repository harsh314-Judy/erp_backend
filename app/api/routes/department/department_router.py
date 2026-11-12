from datetime import date
from uuid import UUID

from fastapi import APIRouter, status

from app.api.db_dependency import PGSessionDep
from app.api.dependencies import CurrentUserDep, DepartmentServiceDep
from app.api.routes.department.department_schemas import (
    DepartmentRead,
    WorkerPatch,
    WorkerRead,
    WorkerWrite,
)
from app.api.routes.user.user_model import Role
from app.api.security.permissions import EDIT_INVENTORY, VIEW_ASSIGNED_WORK, forbid, role_has

router = APIRouter(prefix="/departments", tags=["departments"])


async def _role(session: PGSessionDep, user: CurrentUserDep) -> str:
    role = await session.get(Role, user.role_id)
    return role.role_name if role else ""


@router.get("", response_model=list[DepartmentRead])
async def list_departments(
    service: DepartmentServiceDep,
    session: PGSessionDep,
    user: CurrentUserDep,
    date_from: date | None = None,
    date_to: date | None = None,
) -> list[DepartmentRead]:
    name = await _role(session, user)
    if not role_has(name, VIEW_ASSIGNED_WORK):
        forbid()
    return await service.overview(date_from, date_to, reveal=role_has(name, EDIT_INVENTORY))


@router.get("/workers", response_model=list[WorkerRead])
async def list_workers(
    service: DepartmentServiceDep,
    session: PGSessionDep,
    user: CurrentUserDep,
    include_inactive: bool = False,
) -> list[WorkerRead]:
    name = await _role(session, user)
    if not role_has(name, VIEW_ASSIGNED_WORK):
        forbid()
    return await service.list_workers(include_inactive=include_inactive, reveal=role_has(name, EDIT_INVENTORY))


@router.post("/{operation_id}/workers", response_model=WorkerRead, status_code=status.HTTP_201_CREATED)
async def add_worker(
    operation_id: UUID,
    data: WorkerWrite,
    service: DepartmentServiceDep,
    session: PGSessionDep,
    user: CurrentUserDep,
) -> WorkerRead:
    name = await _role(session, user)
    if not role_has(name, EDIT_INVENTORY):
        forbid()
    return await service.add_worker(operation_id, data, reveal=True)


@router.patch("/workers/{worker_id}", response_model=WorkerRead)
async def update_worker(
    worker_id: UUID,
    data: WorkerPatch,
    service: DepartmentServiceDep,
    session: PGSessionDep,
    user: CurrentUserDep,
) -> WorkerRead:
    name = await _role(session, user)
    if not role_has(name, EDIT_INVENTORY):
        forbid()
    return await service.update_worker(worker_id, data, reveal=True)
