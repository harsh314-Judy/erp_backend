from uuid import UUID

from fastapi import APIRouter, status

from app.api.db_dependency import PGSessionDep
from app.api.dependencies import (
    AttachmentServiceDep,
    CurrentUserDep,
    InvoiceServiceDep,
    SalesOrderServiceDep,
    SalesServiceDep,
)
from app.api.routes.invoice.invoice_schemas import InvoiceDraft, InvoiceIssue, InvoiceRead
from app.api.routes.sales.sales_schemas import (
    PackagingAssign,
    SaleCreate,
    SaleRead,
    SaleUpdate,
    SalesOrderCreate,
    SalesOrderRead,
    SalesOrderStatusUpdate,
)
from app.api.routes.user.user_model import Role
from app.api.security.permissions import MANAGE_SALES, can_see_prices, forbid, role_has
from app.api.schemas.pagination import PaginatedResponse, PaginationDep

router = APIRouter(prefix="/sales", tags=["sales"])


@router.get("/", response_model=PaginatedResponse[SaleRead])
async def list_sales(
    service: SalesServiceDep, pagination: PaginationDep
) -> PaginatedResponse[SaleRead]:
    return await service.list_sales(pagination)


@router.post("/", response_model=SaleRead, status_code=status.HTTP_201_CREATED)
async def create_sale(data: SaleCreate, service: SalesServiceDep) -> SaleRead:
    return await service.create_sale(data)


@router.get("/orders", response_model=list[SalesOrderRead], response_model_exclude_none=True)
async def list_orders(
    service: SalesOrderServiceDep, session: PGSessionDep, user: CurrentUserDep
) -> list[SalesOrderRead]:
    name = await _sales_role(session, user)
    return await service.list_orders(show_prices=can_see_prices(name))


@router.delete("/orders/dispatched")
async def delete_dispatched_orders(
    service: SalesOrderServiceDep, session: PGSessionDep, user: CurrentUserDep
) -> dict[str, int]:
    await _sales_role(session, user)
    return {"deleted": await service.delete_dispatched()}


@router.post("/orders", response_model=SalesOrderRead, status_code=status.HTTP_201_CREATED)
async def create_order(
    data: SalesOrderCreate,
    service: SalesOrderServiceDep,
    session: PGSessionDep,
    user: CurrentUserDep,
) -> SalesOrderRead:
    name = await _sales_role(session, user)
    return await service.create_order(data, user, show_prices=can_see_prices(name))


@router.get("/orders/{order_id}", response_model=SalesOrderRead, response_model_exclude_none=True)
async def get_order(
    order_id: UUID,
    service: SalesOrderServiceDep,
    session: PGSessionDep,
    user: CurrentUserDep,
) -> SalesOrderRead:
    name = await _sales_role(session, user)
    return await service.get_order(order_id, show_prices=can_see_prices(name))


@router.post("/orders/{order_id}/packaging", response_model=SalesOrderRead)
async def assign_packaging(
    order_id: UUID,
    data: PackagingAssign,
    service: SalesOrderServiceDep,
    session: PGSessionDep,
    user: CurrentUserDep,
) -> SalesOrderRead:
    name = await _sales_role(session, user)
    return await service.assign_packaging(
        order_id, data.packaging_user_id, show_prices=can_see_prices(name)
    )


@router.patch("/orders/{order_id}", response_model=SalesOrderRead, response_model_exclude_none=True)
async def update_order_status(
    order_id: UUID,
    data: SalesOrderStatusUpdate,
    service: SalesOrderServiceDep,
    session: PGSessionDep,
    user: CurrentUserDep,
) -> SalesOrderRead:
    name = await _sales_role(session, user)
    return await service.set_status(order_id, data.status, user, show_prices=can_see_prices(name))


@router.post("/orders/{order_id}/dispatch", response_model=SalesOrderRead)
async def dispatch_order(
    order_id: UUID,
    service: SalesOrderServiceDep,
    session: PGSessionDep,
    user: CurrentUserDep,
) -> SalesOrderRead:
    name = await _sales_role(session, user)
    return await service.dispatch(order_id, user, show_prices=can_see_prices(name))


@router.get("/orders/{order_id}/invoice-draft", response_model=InvoiceDraft)
async def invoice_draft(
    order_id: UUID,
    service: InvoiceServiceDep,
    session: PGSessionDep,
    user: CurrentUserDep,
) -> InvoiceDraft:
    await _sales_role(session, user)
    return await service.draft_for_order(order_id)


@router.post("/orders/{order_id}/invoice", response_model=InvoiceRead, status_code=status.HTTP_201_CREATED)
async def issue_invoice(
    order_id: UUID,
    data: InvoiceIssue,
    service: InvoiceServiceDep,
    attachments: AttachmentServiceDep,
    session: PGSessionDep,
    user: CurrentUserDep,
) -> InvoiceRead:
    await _sales_role(session, user)
    return await service.issue_for_order(order_id, data, user, attachments)


@router.get("/{sale_id}", response_model=SaleRead)
async def get_sale(sale_id: UUID, service: SalesServiceDep) -> SaleRead:
    return await service.get_sale(sale_id)


@router.patch("/{sale_id}", response_model=SaleRead)
async def update_sale(
    sale_id: UUID, data: SaleUpdate, service: SalesServiceDep
) -> SaleRead:
    return await service.update_sale(sale_id, data)


@router.delete("/{sale_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_sale(sale_id: UUID, service: SalesServiceDep) -> None:
    await service.delete_sale(sale_id)


async def _sales_role(session: PGSessionDep, user: CurrentUserDep) -> str:
    role = await session.get(Role, user.role_id)
    name = role.role_name if role else ""
    if not role_has(name, MANAGE_SALES):
        forbid()
    return name
