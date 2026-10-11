from uuid import UUID

from fastapi import APIRouter, status

from app.api.dependencies import PurchaseOrderServiceDep
from app.api.routes.purchase_order.purchase_order_schemas import (
    PurchaseOrderProductCreate,
    PurchaseOrderProductRead,
    PurchaseOrderProductUpdate,
    PurchaseOrderRawMaterialCreate,
    PurchaseOrderRawMaterialRead,
    PurchaseOrderRawMaterialUpdate,
)
from app.api.schemas.pagination import PaginatedResponse, PaginationDep

router = APIRouter(tags=["purchase orders"])


@router.get(
    "/purchase-orders/raw-materials",
    response_model=PaginatedResponse[PurchaseOrderRawMaterialRead],
)
async def list_material_orders(
    service: PurchaseOrderServiceDep, pagination: PaginationDep
) -> PaginatedResponse[PurchaseOrderRawMaterialRead]:
    return await service.list_material_orders(pagination)


@router.post(
    "/purchase-orders/raw-materials",
    response_model=PurchaseOrderRawMaterialRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_material_order(
    data: PurchaseOrderRawMaterialCreate, service: PurchaseOrderServiceDep
) -> PurchaseOrderRawMaterialRead:
    return await service.create_material_order(data)


@router.get(
    "/purchase-orders/raw-materials/{order_id}",
    response_model=PurchaseOrderRawMaterialRead,
)
async def get_material_order(
    order_id: UUID, service: PurchaseOrderServiceDep
) -> PurchaseOrderRawMaterialRead:
    return await service.get_material_order(order_id)


@router.patch(
    "/purchase-orders/raw-materials/{order_id}",
    response_model=PurchaseOrderRawMaterialRead,
)
async def update_material_order(
    order_id: UUID,
    data: PurchaseOrderRawMaterialUpdate,
    service: PurchaseOrderServiceDep,
) -> PurchaseOrderRawMaterialRead:
    return await service.update_material_order(order_id, data)


@router.delete(
    "/purchase-orders/raw-materials/{order_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_material_order(order_id: UUID, service: PurchaseOrderServiceDep) -> None:
    await service.delete_material_order(order_id)


@router.get(
    "/purchase-orders/products",
    response_model=PaginatedResponse[PurchaseOrderProductRead],
)
async def list_product_orders(
    service: PurchaseOrderServiceDep, pagination: PaginationDep
) -> PaginatedResponse[PurchaseOrderProductRead]:
    return await service.list_product_orders(pagination)


@router.post(
    "/purchase-orders/products",
    response_model=PurchaseOrderProductRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_product_order(
    data: PurchaseOrderProductCreate, service: PurchaseOrderServiceDep
) -> PurchaseOrderProductRead:
    return await service.create_product_order(data)


@router.get(
    "/purchase-orders/products/{order_id}",
    response_model=PurchaseOrderProductRead,
)
async def get_product_order(
    order_id: UUID, service: PurchaseOrderServiceDep
) -> PurchaseOrderProductRead:
    return await service.get_product_order(order_id)


@router.patch(
    "/purchase-orders/products/{order_id}",
    response_model=PurchaseOrderProductRead,
)
async def update_product_order(
    order_id: UUID,
    data: PurchaseOrderProductUpdate,
    service: PurchaseOrderServiceDep,
) -> PurchaseOrderProductRead:
    return await service.update_product_order(order_id, data)


@router.delete(
    "/purchase-orders/products/{order_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_product_order(order_id: UUID, service: PurchaseOrderServiceDep) -> None:
    await service.delete_product_order(order_id)
