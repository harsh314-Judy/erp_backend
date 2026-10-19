from uuid import UUID

from fastapi import APIRouter, Query, status

from app.api.dependencies import CurrentUserDep, ProductServiceDep, PGSessionDep
from app.api.routes.product.product_schemas import (
    ComponentRead,
    ComponentWrite,
    MeasurementUnitCreate,
    MeasurementUnitRead,
    MeasurementUnitUpdate,
    ProductCategoryCreate,
    ProductCategoryRead,
    ProductCategoryUpdate,
    ProductCreate,
    ProductOption,
    ProductRead,
    ProductUpdate,
    RouteWrite,
)
from app.api.routes.user.user_model import Role
from app.api.schemas.pagination import PaginatedResponse, PaginationDep
from app.api.security.permissions import (
    EDIT_INVENTORY,
    VIEW_INVENTORY,
    can_see_prices,
    role_has,
)
from app.api.security.permissions import forbid

router = APIRouter(tags=["products"])


async def _role_name(session: PGSessionDep, user: CurrentUserDep) -> str:
    role = await session.get(Role, user.role_id)
    return role.role_name if role else ""


async def _viewer(session: PGSessionDep, user: CurrentUserDep) -> str:
    name = await _role_name(session, user)
    if not role_has(name, VIEW_INVENTORY):
        forbid()
    return name


async def _editor(session: PGSessionDep, user: CurrentUserDep) -> str:
    name = await _role_name(session, user)
    if not role_has(name, EDIT_INVENTORY):
        forbid()
    return name


@router.get("/measurement-units", response_model=PaginatedResponse[MeasurementUnitRead])
async def list_units(
    service: ProductServiceDep, pagination: PaginationDep
) -> PaginatedResponse[MeasurementUnitRead]:
    return await service.list_units(pagination)


@router.post(
    "/measurement-units",
    response_model=MeasurementUnitRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_unit(
    data: MeasurementUnitCreate, service: ProductServiceDep
) -> MeasurementUnitRead:
    return await service.create_unit(data)


@router.patch("/measurement-units/{unit_id}", response_model=MeasurementUnitRead)
async def update_unit(
    unit_id: UUID, data: MeasurementUnitUpdate, service: ProductServiceDep
) -> MeasurementUnitRead:
    return await service.update_unit(unit_id, data)


@router.delete("/measurement-units/{unit_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_unit(unit_id: UUID, service: ProductServiceDep) -> None:
    await service.delete_unit(unit_id)


@router.get("/product-categories", response_model=PaginatedResponse[ProductCategoryRead])
async def list_categories(
    service: ProductServiceDep, pagination: PaginationDep
) -> PaginatedResponse[ProductCategoryRead]:
    return await service.list_categories(pagination)


@router.post(
    "/product-categories",
    response_model=ProductCategoryRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_category(
    data: ProductCategoryCreate, service: ProductServiceDep
) -> ProductCategoryRead:
    return await service.create_category(data)


@router.patch("/product-categories/{category_id}", response_model=ProductCategoryRead)
async def update_category(
    category_id: UUID, data: ProductCategoryUpdate, service: ProductServiceDep
) -> ProductCategoryRead:
    return await service.update_category(category_id, data)


@router.delete("/product-categories/{category_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_category(category_id: UUID, service: ProductServiceDep) -> None:
    await service.delete_category(category_id)


@router.get("/products/options", response_model=list[ProductOption])
async def product_options(
    service: ProductServiceDep,
    session: PGSessionDep,
    user: CurrentUserDep,
    q: str | None = None,
) -> list[ProductOption]:
    await _viewer(session, user)
    return await service.options(q)


@router.get(
    "/products",
    response_model=PaginatedResponse[ProductRead],
    response_model_exclude_none=True,
)
async def list_products(
    service: ProductServiceDep,
    pagination: PaginationDep,
    session: PGSessionDep,
    user: CurrentUserDep,
    q: str | None = None,
    brief: bool = False,
) -> PaginatedResponse[ProductRead]:
    role_name = await _viewer(session, user)
    return await service.list_products(
        pagination, query=q, show_prices=can_see_prices(role_name), brief=brief
    )


@router.post(
    "/products",
    response_model=ProductRead,
    status_code=status.HTTP_201_CREATED,
    response_model_exclude_none=True,
)
async def create_product(
    data: ProductCreate,
    service: ProductServiceDep,
    session: PGSessionDep,
    user: CurrentUserDep,
) -> ProductRead:
    role_name = await _editor(session, user)
    return await service.create_product(data, show_prices=can_see_prices(role_name))


@router.get(
    "/products/{product_id}",
    response_model=ProductRead,
    response_model_exclude_none=True,
)
async def get_product(
    product_id: UUID,
    service: ProductServiceDep,
    session: PGSessionDep,
    user: CurrentUserDep,
) -> ProductRead:
    role_name = await _viewer(session, user)
    return await service.get_product(product_id, show_prices=can_see_prices(role_name))


@router.put("/products/{product_id}/route", response_model=list[UUID])
async def replace_route(
    product_id: UUID,
    data: RouteWrite,
    service: ProductServiceDep,
    session: PGSessionDep,
    user: CurrentUserDep,
) -> list[UUID]:
    await _editor(session, user)
    return await service.replace_route(product_id, data.operation_ids)


@router.get("/products/{product_id}/route", response_model=list[UUID])
async def get_route(
    product_id: UUID,
    service: ProductServiceDep,
    session: PGSessionDep,
    user: CurrentUserDep,
) -> list[UUID]:
    await _viewer(session, user)
    return await service.list_route(product_id)


@router.put("/products/{product_id}/recipe", response_model=list[ComponentRead])
async def replace_recipe(
    product_id: UUID,
    items: list[ComponentWrite],
    service: ProductServiceDep,
    session: PGSessionDep,
    user: CurrentUserDep,
) -> list[ComponentRead]:
    await _editor(session, user)
    return await service.replace_recipe(product_id, items)


@router.get("/products/{product_id}/recipe", response_model=list[ComponentRead])
async def get_recipe(
    product_id: UUID,
    service: ProductServiceDep,
    session: PGSessionDep,
    user: CurrentUserDep,
) -> list[ComponentRead]:
    await _viewer(session, user)
    return await service.list_recipe(product_id)


@router.patch(
    "/products/{product_id}",
    response_model=ProductRead,
    response_model_exclude_none=True,
)
async def update_product(
    product_id: UUID,
    data: ProductUpdate,
    service: ProductServiceDep,
    session: PGSessionDep,
    user: CurrentUserDep,
) -> ProductRead:
    role_name = await _editor(session, user)
    return await service.update_product(
        product_id, data, show_prices=can_see_prices(role_name)
    )


@router.delete("/products/{product_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_product(
    product_id: UUID,
    service: ProductServiceDep,
    session: PGSessionDep,
    user: CurrentUserDep,
) -> None:
    await _editor(session, user)
    await service.delete_product(product_id)
