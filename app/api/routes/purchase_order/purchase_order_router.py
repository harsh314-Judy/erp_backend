from uuid import UUID

from fastapi import APIRouter, status

from app.api.db_dependency import PGSessionDep
from app.api.dependencies import CurrentUserDep, PurchaseFlowServiceDep, PurchaseOrderServiceDep
from app.api.routes.user.user_model import Role
from app.api.security.permissions import (
    MANAGE_PURCHASING,
    VIEW_ASSIGNED_WORK,
    can_see_prices,
    forbid,
    role_has,
)
from app.api.routes.purchase_order.purchase_order_schemas import (
    PurchaseOrderProductCreate,
    PurchaseOrderProductRead,
    PurchaseOrderProductUpdate,
    PurchaseOrderRawMaterialCreate,
    PurchaseOrderRawMaterialRead,
    PurchaseOrderRawMaterialUpdate,
    PurchaseOrderUpdate,
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


async def _purchase_role(session: PGSessionDep, user: CurrentUserDep) -> str:
    role = await session.get(Role, user.role_id)
    name = role.role_name if role else ""
    if not (role_has(name, MANAGE_PURCHASING) or role_has(name, VIEW_ASSIGNED_WORK)):
        forbid()
    return name


@router.get("/purchase-orders")
async def list_purchase_orders(
    service: PurchaseFlowServiceDep, session: PGSessionDep, user: CurrentUserDep
) -> list[dict]:
    name = await _purchase_role(session, user)
    staff = name == "staff"
    return await service.list_orders(show_prices=can_see_prices(name), staff_view=staff)


@router.get("/purchase-requests")
async def list_purchase_requests(
    service: PurchaseFlowServiceDep, session: PGSessionDep, user: CurrentUserDep
) -> list[dict]:
    name = await _purchase_role(session, user)
    if not role_has(name, MANAGE_PURCHASING):
        forbid()
    return await service.list_requests()


@router.post("/purchase-orders", status_code=status.HTTP_201_CREATED)
async def create_purchase_order(
    data: dict,
    service: PurchaseFlowServiceDep,
    session: PGSessionDep,
    user: CurrentUserDep,
) -> dict:
    name = await _purchase_role(session, user)
    if not role_has(name, MANAGE_PURCHASING):
        forbid()
    return await service.create_order(data, user)


@router.patch("/purchase-orders/{order_id}")
async def update_purchase_order(
    order_id: UUID,
    data: PurchaseOrderUpdate,
    service: PurchaseFlowServiceDep,
    session: PGSessionDep,
    user: CurrentUserDep,
) -> dict:
    name = await _purchase_role(session, user)
    if not role_has(name, MANAGE_PURCHASING):
        forbid()
    return await service.update_order(order_id, data, user)


@router.post("/purchase-orders/{order_id}/arrived")
async def mark_purchase_arrived(
    order_id: UUID,
    data: dict,
    service: PurchaseFlowServiceDep,
    session: PGSessionDep,
    user: CurrentUserDep,
) -> dict:
    name = await _purchase_role(session, user)
    if not role_has(name, MANAGE_PURCHASING):
        forbid()
    return await service.mark_arrived(order_id, data)


@router.post("/purchase-orders/{order_id}/verify")
async def verify_purchase_order(
    order_id: UUID,
    data: dict,
    service: PurchaseFlowServiceDep,
    session: PGSessionDep,
    user: CurrentUserDep,
) -> dict:
    name = await _purchase_role(session, user)
    if not role_has(name, MANAGE_PURCHASING):
        forbid()
    return await service.verify(order_id, user, data.get("plate_mismatch_note"))
