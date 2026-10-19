from uuid import UUID

from fastapi import APIRouter, status

from app.api.db_dependency import PGSessionDep
from app.api.dependencies import CurrentUserDep, RawMaterialServiceDep
from app.api.routes.raw_material.raw_material_schemas import (
    RawMaterialCategoryCreate,
    RawMaterialCategoryRead,
    RawMaterialCreate,
    RawMaterialOption,
    RawMaterialRead,
    RawMaterialUpdate,
)
from app.api.routes.user.user_model import Role
from app.api.schemas.pagination import PaginatedResponse, PaginationDep
from app.api.security.permissions import EDIT_INVENTORY, VIEW_INVENTORY, can_see_prices, forbid, role_has

router = APIRouter(prefix="/raw-materials", tags=["raw materials"])


@router.get("/categories", response_model=PaginatedResponse[RawMaterialCategoryRead])
async def list_categories(
    service: RawMaterialServiceDep, pagination: PaginationDep
) -> PaginatedResponse[RawMaterialCategoryRead]:
    return await service.list_categories(pagination)


@router.post(
    "/categories",
    response_model=RawMaterialCategoryRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_category(
    data: RawMaterialCategoryCreate, service: RawMaterialServiceDep
) -> RawMaterialCategoryRead:
    return await service.create_category(data)


@router.delete("/categories/{category_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_category(category_id: UUID, service: RawMaterialServiceDep) -> None:
    await service.delete_category(category_id)


async def _role(session: PGSessionDep, user: CurrentUserDep, capability: str) -> str:
    role = await session.get(Role, user.role_id)
    name = role.role_name if role else ""
    if not role_has(name, capability):
        forbid()
    return name


@router.get("/options", response_model=list[RawMaterialOption])
async def material_options(
    service: RawMaterialServiceDep,
    session: PGSessionDep,
    user: CurrentUserDep,
    q: str | None = None,
) -> list[RawMaterialOption]:
    await _role(session, user, VIEW_INVENTORY)
    return await service.options(q)


@router.get("/", response_model=PaginatedResponse[RawMaterialRead], response_model_exclude_none=True)
async def list_materials(
    service: RawMaterialServiceDep,
    pagination: PaginationDep,
    session: PGSessionDep,
    user: CurrentUserDep,
    q: str | None = None,
    brief: bool = False,
) -> PaginatedResponse[RawMaterialRead]:
    role_name = await _role(session, user, VIEW_INVENTORY)
    return await service.list_materials(
        pagination, query=q, show_prices=can_see_prices(role_name), brief=brief
    )


@router.post("/", response_model=RawMaterialRead, status_code=status.HTTP_201_CREATED, response_model_exclude_none=True)
async def create_material(
    data: RawMaterialCreate,
    service: RawMaterialServiceDep,
    session: PGSessionDep,
    user: CurrentUserDep,
) -> RawMaterialRead:
    role_name = await _role(session, user, EDIT_INVENTORY)
    return await service.create_material(data, show_prices=can_see_prices(role_name))


@router.get("/{material_id}", response_model=RawMaterialRead, response_model_exclude_none=True)
async def get_material(
    material_id: UUID,
    service: RawMaterialServiceDep,
    session: PGSessionDep,
    user: CurrentUserDep,
) -> RawMaterialRead:
    role_name = await _role(session, user, VIEW_INVENTORY)
    return await service.get_material(material_id, show_prices=can_see_prices(role_name))


@router.patch("/{material_id}", response_model=RawMaterialRead, response_model_exclude_none=True)
async def update_material(
    material_id: UUID,
    data: RawMaterialUpdate,
    service: RawMaterialServiceDep,
    session: PGSessionDep,
    user: CurrentUserDep,
) -> RawMaterialRead:
    role_name = await _role(session, user, EDIT_INVENTORY)
    return await service.update_material(material_id, data, show_prices=can_see_prices(role_name))


@router.delete("/{material_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_material(
    material_id: UUID,
    service: RawMaterialServiceDep,
    session: PGSessionDep,
    user: CurrentUserDep,
) -> None:
    await _role(session, user, EDIT_INVENTORY)
    await service.delete_material(material_id)
