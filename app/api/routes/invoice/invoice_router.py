from uuid import UUID

from fastapi import APIRouter, status

from app.api.db_dependency import PGSessionDep
from app.api.dependencies import CurrentUserDep, InvoiceServiceDep
from app.api.routes.invoice.invoice_schemas import InvoiceRead, PaymentCreate
from app.api.routes.user.user_model import Role
from app.api.security.permissions import MANAGE_SALES, forbid, role_has

router = APIRouter(prefix="/invoices", tags=["invoices"])


async def _sales(session: PGSessionDep, user: CurrentUserDep) -> None:
    role = await session.get(Role, user.role_id)
    if not role_has(role.role_name if role else None, MANAGE_SALES):
        forbid()


@router.get("", response_model=list[InvoiceRead])
async def list_invoices(
    service: InvoiceServiceDep, session: PGSessionDep, user: CurrentUserDep
) -> list[InvoiceRead]:
    await _sales(session, user)
    return await service.list_invoices()


@router.get("/{invoice_id}", response_model=InvoiceRead)
async def get_invoice(
    invoice_id: UUID,
    service: InvoiceServiceDep,
    session: PGSessionDep,
    user: CurrentUserDep,
) -> InvoiceRead:
    await _sales(session, user)
    return await service.get_invoice(invoice_id)


@router.post("/{invoice_id}/payments", response_model=InvoiceRead, status_code=status.HTTP_201_CREATED)
async def add_payment(
    invoice_id: UUID,
    data: PaymentCreate,
    service: InvoiceServiceDep,
    session: PGSessionDep,
    user: CurrentUserDep,
) -> InvoiceRead:
    await _sales(session, user)
    return await service.add_payment(invoice_id, data, user)
