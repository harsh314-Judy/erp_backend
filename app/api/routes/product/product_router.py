from uuid import UUID

from fastapi import APIRouter, status

from app.api.dependencies import ProductServiceDep
from app.api.routes.product.product_schemas import (
    MeasurementUnitCreate,
    MeasurementUnitRead,
    MeasurementUnitUpdate,
    ProductCategoryCreate,
    ProductCategoryRead,
    ProductCategoryUpdate,
    ProductCreate,
    ProductRead,
    ProductUpdate,
)
from app.api.schemas.pagination import PaginatedResponse, PaginationDep

router = APIRouter(tags=["products"])


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


@router.get("/products", response_model=PaginatedResponse[ProductRead])
async def list_products(
    service: ProductServiceDep, pagination: PaginationDep
) -> PaginatedResponse[ProductRead]:
    return await service.list_products(pagination)


@router.post("/products", response_model=ProductRead, status_code=status.HTTP_201_CREATED)
async def create_product(data: ProductCreate, service: ProductServiceDep) -> ProductRead:
    return await service.create_product(data)


@router.get("/products/{product_id}", response_model=ProductRead)
async def get_product(product_id: UUID, service: ProductServiceDep) -> ProductRead:
    return await service.get_product(product_id)


@router.patch("/products/{product_id}", response_model=ProductRead)
async def update_product(
    product_id: UUID, data: ProductUpdate, service: ProductServiceDep
) -> ProductRead:
    return await service.update_product(product_id, data)


@router.delete("/products/{product_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_product(product_id: UUID, service: ProductServiceDep) -> None:
    await service.delete_product(product_id)
