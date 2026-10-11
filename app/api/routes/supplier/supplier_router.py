from uuid import UUID

from fastapi import APIRouter, status

from app.api.dependencies import SupplierServiceDep
from app.api.routes.supplier.supplier_schemas import (
    ProductSupplierCreate,
    ProductSupplierRead,
    ProductSupplierUpdate,
    RawMaterialSupplierCreate,
    RawMaterialSupplierRead,
    RawMaterialSupplierUpdate,
    SupplierCreate,
    SupplierRead,
    SupplierUpdate,
)
from app.api.schemas.pagination import PaginatedResponse, PaginationDep

router = APIRouter(tags=["suppliers"])


@router.get("/suppliers", response_model=PaginatedResponse[SupplierRead])
async def list_suppliers(
    service: SupplierServiceDep, pagination: PaginationDep
) -> PaginatedResponse[SupplierRead]:
    return await service.list_suppliers(pagination)


@router.post("/suppliers", response_model=SupplierRead, status_code=status.HTTP_201_CREATED)
async def create_supplier(data: SupplierCreate, service: SupplierServiceDep) -> SupplierRead:
    return await service.create_supplier(data)


@router.get("/suppliers/{supplier_id}", response_model=SupplierRead)
async def get_supplier(supplier_id: UUID, service: SupplierServiceDep) -> SupplierRead:
    return await service.get_supplier(supplier_id)


@router.patch("/suppliers/{supplier_id}", response_model=SupplierRead)
async def update_supplier(
    supplier_id: UUID, data: SupplierUpdate, service: SupplierServiceDep
) -> SupplierRead:
    return await service.update_supplier(supplier_id, data)


@router.delete("/suppliers/{supplier_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_supplier(supplier_id: UUID, service: SupplierServiceDep) -> None:
    await service.delete_supplier(supplier_id)


@router.get(
    "/raw-material-suppliers",
    response_model=PaginatedResponse[RawMaterialSupplierRead],
)
async def list_material_links(
    service: SupplierServiceDep, pagination: PaginationDep
) -> PaginatedResponse[RawMaterialSupplierRead]:
    return await service.list_material_links(pagination)


@router.post(
    "/raw-material-suppliers",
    response_model=RawMaterialSupplierRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_material_link(
    data: RawMaterialSupplierCreate, service: SupplierServiceDep
) -> RawMaterialSupplierRead:
    return await service.create_material_link(data)


@router.patch("/raw-material-suppliers/{link_id}", response_model=RawMaterialSupplierRead)
async def update_material_link(
    link_id: UUID, data: RawMaterialSupplierUpdate, service: SupplierServiceDep
) -> RawMaterialSupplierRead:
    return await service.update_material_link(link_id, data)


@router.delete("/raw-material-suppliers/{link_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_material_link(link_id: UUID, service: SupplierServiceDep) -> None:
    await service.delete_material_link(link_id)


@router.get("/product-suppliers", response_model=PaginatedResponse[ProductSupplierRead])
async def list_product_links(
    service: SupplierServiceDep, pagination: PaginationDep
) -> PaginatedResponse[ProductSupplierRead]:
    return await service.list_product_links(pagination)


@router.post(
    "/product-suppliers",
    response_model=ProductSupplierRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_product_link(
    data: ProductSupplierCreate, service: SupplierServiceDep
) -> ProductSupplierRead:
    return await service.create_product_link(data)


@router.patch("/product-suppliers/{link_id}", response_model=ProductSupplierRead)
async def update_product_link(
    link_id: UUID, data: ProductSupplierUpdate, service: SupplierServiceDep
) -> ProductSupplierRead:
    return await service.update_product_link(link_id, data)


@router.delete("/product-suppliers/{link_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_product_link(link_id: UUID, service: SupplierServiceDep) -> None:
    await service.delete_product_link(link_id)
