from uuid import UUID

from fastapi import APIRouter, File, HTTPException, UploadFile, status
from fastapi.responses import Response

from app.api.db_dependency import PGSessionDep
from app.api.dependencies import AttachmentServiceDep, CurrentUserDep, InvoiceServiceDep
from app.api.routes.invoice.invoice_model import Payment
from app.api.routes.invoice.invoice_schemas import InvoiceRead, PaymentCreate
from app.api.routes.user.user_model import Role
from app.api.security.permissions import MANAGE_SALES, VIEW_FINANCIALS, forbid, role_has

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


@router.get("/{invoice_id}/pdf")
async def download_invoice_pdf(
    invoice_id: UUID,
    service: InvoiceServiceDep,
    attachments: AttachmentServiceDep,
    session: PGSessionDep,
    user: CurrentUserDep,
) -> Response:
    await _sales(session, user)
    payload, filename = await service.pdf_file(invoice_id, attachments)
    return Response(
        content=payload,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


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


@router.post("/{invoice_id}/payments/{payment_id}/photo", status_code=status.HTTP_204_NO_CONTENT)
async def replace_invoice_payment_photo(
    invoice_id: UUID,
    payment_id: UUID,
    session: PGSessionDep,
    user: CurrentUserDep,
    attachments: AttachmentServiceDep,
    file: UploadFile = File(...),
) -> None:
    role = await session.get(Role, user.role_id)
    if not role_has(role.role_name if role else None, VIEW_FINANCIALS):
        forbid()
    payment = await session.get(Payment, payment_id)
    if payment is None or payment.invoice_id != invoice_id:
        raise HTTPException(status_code=404, detail="Payment not found")
    await attachments.replace_linked_photo(session, payment, file, user)
