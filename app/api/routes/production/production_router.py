from uuid import UUID

from fastapi import APIRouter, status

from app.api.db_dependency import PGSessionDep
from app.api.dependencies import CurrentUserDep, ProductionServiceDep
from app.api.routes.production.production_schemas import (
    JobApprove,
    JobCancel,
    ProductionJobCreate,
    ProductionJobDetail,
    ProductionJobRead,
    StageComplete,
)
from app.api.routes.user.user_model import Role
from app.api.schemas.pagination import PaginatedResponse, PaginationDep
from app.api.security.permissions import (
    APPROVE_JOBS,
    EDIT_INVENTORY,
    VIEW_ASSIGNED_WORK,
    forbid,
    role_has,
)

router = APIRouter(prefix="/production-jobs", tags=["production"])


async def _role(session: PGSessionDep, user: CurrentUserDep) -> str:
    role = await session.get(Role, user.role_id)
    return role.role_name if role else ""


@router.get("/", response_model=PaginatedResponse[ProductionJobRead])
async def list_jobs(
    service: ProductionServiceDep,
    pagination: PaginationDep,
    session: PGSessionDep,
    user: CurrentUserDep,
) -> PaginatedResponse[ProductionJobRead]:
    name = await _role(session, user)
    if not (role_has(name, VIEW_ASSIGNED_WORK) or role_has(name, EDIT_INVENTORY) or role_has(name, APPROVE_JOBS)):
        forbid()
    return await service.list_jobs(pagination, user)


@router.post("/", response_model=ProductionJobDetail, status_code=status.HTTP_201_CREATED)
async def create_job(
    data: ProductionJobCreate,
    service: ProductionServiceDep,
    session: PGSessionDep,
    user: CurrentUserDep,
) -> ProductionJobDetail:
    name = await _role(session, user)
    if not role_has(name, EDIT_INVENTORY):
        forbid()
    return await service.create_job(data, user)


@router.get("/{job_id}", response_model=ProductionJobDetail)
async def get_job(
    job_id: UUID,
    service: ProductionServiceDep,
    session: PGSessionDep,
    user: CurrentUserDep,
) -> ProductionJobDetail:
    name = await _role(session, user)
    if not (role_has(name, VIEW_ASSIGNED_WORK) or role_has(name, EDIT_INVENTORY)):
        forbid()
    return await service.get_job(job_id, user)


@router.post("/{job_id}/start", response_model=ProductionJobDetail)
async def start_job(
    job_id: UUID,
    service: ProductionServiceDep,
    session: PGSessionDep,
    user: CurrentUserDep,
) -> ProductionJobDetail:
    name = await _role(session, user)
    if not (role_has(name, EDIT_INVENTORY) or role_has(name, VIEW_ASSIGNED_WORK)):
        forbid()
    return await service.start_job(job_id, user)


@router.post("/{job_id}/stages/{stage_id}/complete", response_model=ProductionJobDetail)
async def complete_stage(
    job_id: UUID,
    stage_id: UUID,
    data: StageComplete,
    service: ProductionServiceDep,
    session: PGSessionDep,
    user: CurrentUserDep,
) -> ProductionJobDetail:
    name = await _role(session, user)
    if not role_has(name, VIEW_ASSIGNED_WORK) and not role_has(name, EDIT_INVENTORY):
        forbid()
    return await service.complete_stage(job_id, stage_id, data, user)


@router.post("/{job_id}/approve", response_model=ProductionJobDetail)
async def approve_job(
    job_id: UUID,
    data: JobApprove,
    service: ProductionServiceDep,
    session: PGSessionDep,
    user: CurrentUserDep,
) -> ProductionJobDetail:
    name = await _role(session, user)
    if not role_has(name, APPROVE_JOBS):
        forbid()
    return await service.approve(job_id, data, user)


@router.post("/{job_id}/cancel", response_model=ProductionJobDetail)
async def cancel_job(
    job_id: UUID,
    data: JobCancel,
    service: ProductionServiceDep,
    session: PGSessionDep,
    user: CurrentUserDep,
) -> ProductionJobDetail:
    name = await _role(session, user)
    if not (role_has(name, APPROVE_JOBS) or role_has(name, EDIT_INVENTORY)):
        forbid()
    return await service.cancel(job_id, data, user)
