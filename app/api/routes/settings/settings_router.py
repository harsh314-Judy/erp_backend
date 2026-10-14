from fastapi import APIRouter

from app.api.db_dependency import PGSessionDep
from app.api.dependencies import CurrentUserDep, SettingsServiceDep
from app.api.routes.settings.settings_schemas import CompanyRead, CompanyUpdate
from app.api.routes.user.user_model import Role
from app.api.security.permissions import MANAGE_COMPANY, forbid, role_has

router = APIRouter(tags=["settings"])


@router.get("/company", response_model=CompanyRead)
async def get_company(service: SettingsServiceDep, _: CurrentUserDep) -> CompanyRead:
    return await service.get_company()


@router.patch("/company", response_model=CompanyRead)
async def update_company(
    data: CompanyUpdate,
    service: SettingsServiceDep,
    session: PGSessionDep,
    user: CurrentUserDep,
) -> CompanyRead:
    role = await session.get(Role, user.role_id)
    if not role_has(role.role_name if role else None, MANAGE_COMPANY):
        forbid()
    return await service.update_company(data)
