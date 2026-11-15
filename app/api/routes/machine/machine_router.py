from uuid import UUID

from fastapi import APIRouter, status

from app.api.db_dependency import PGSessionDep
from app.api.dependencies import CurrentUserDep, MachineServiceDep
from app.api.routes.machine.machine_schemas import MachineCreate, MachineRead, MachineUpdate
from app.api.routes.user.user_model import Role
from app.api.security.permissions import EDIT_INVENTORY, VIEW_ASSIGNED_WORK, forbid, role_has

router = APIRouter(prefix="/machines", tags=["machines"])


async def _role(session: PGSessionDep, user: CurrentUserDep) -> str:
    role = await session.get(Role, user.role_id)
    return role.role_name if role else ""


@router.get("", response_model=list[MachineRead])
async def list_machines(
    service: MachineServiceDep,
    session: PGSessionDep,
    user: CurrentUserDep,
    operation_id: UUID | None = None,
) -> list[MachineRead]:
    name = await _role(session, user)
    if not role_has(name, VIEW_ASSIGNED_WORK):
        forbid()
    return await service.list_machines(operation_id)


@router.post("", response_model=MachineRead, status_code=status.HTTP_201_CREATED)
async def create_machine(
    data: MachineCreate,
    service: MachineServiceDep,
    session: PGSessionDep,
    user: CurrentUserDep,
) -> MachineRead:
    name = await _role(session, user)
    if not role_has(name, EDIT_INVENTORY):
        forbid()
    return await service.create_machine(data)


@router.patch("/{machine_id}", response_model=MachineRead)
async def update_machine(
    machine_id: UUID,
    data: MachineUpdate,
    service: MachineServiceDep,
    session: PGSessionDep,
    user: CurrentUserDep,
) -> MachineRead:
    name = await _role(session, user)
    if not role_has(name, EDIT_INVENTORY):
        forbid()
    return await service.update_machine(machine_id, data)
