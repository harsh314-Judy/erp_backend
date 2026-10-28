from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID
from zoneinfo import ZoneInfo

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import delete, select

from app.api.routes.attachment.attachment_model import Attachment
from app.api.routes.attachment.attachment_services import AttachmentService
from app.api.routes.customer.customer_model import Customer
from app.api.routes.invoice.gst import financial_year, money, qty, split_gst
from app.api.routes.invoice.invoice_model import Invoice, InvoiceLine, InvoiceSequence, Payment
from app.api.routes.invoice.invoice_pdf import SELLER_NAME, Bill, BillLine, render_invoice_pdf
from app.api.routes.invoice.invoice_schemas import (
    InvoiceDraft,
    InvoiceDraftLine,
    InvoiceIssue,
    InvoiceRead,
    PaymentCreate,
    PaymentRead,
)
from app.api.routes.product.product_model import MeasurementUnit, Product
from app.api.routes.sales.sales_model import SalesOrder, SalesOrderLine
from app.api.routes.settings.settings_model import CompanySettings
from app.api.routes.user.user_model import User
from app.config import auth_settings
from app.db.repository import commit_or_conflict, get_or_404

_MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


class InvoiceService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create_for_order(
        self,
        order: SalesOrder,
        lines: list[SalesOrderLine],
        customer: Customer,
        products: dict[UUID, Product],
        company: CompanySettings,
    ) -> Invoice:
        same_state = _same_state(company.state, customer.state)
        number = await self._next_number(company.invoice_prefix)
        invoice = Invoice(
            sales_order_id=order.id,
            customer_id=customer.id,
            number=number,
            same_state=same_state,
            delivery_charge=money(order.delivery_charge),
        )
        self.session.add(invoice)
        await self.session.flush()
        taxable = money(0)
        cgst = money(0)
        sgst = money(0)
        igst = money(0)
        for line in lines:
            product = products[line.product_id]
            line_taxable = money(line.quantity * line.unit_price)
            rate = product.gst_percent if product.gst else 0
            line_cgst, line_sgst, line_igst = split_gst(rate, line_taxable, same_state=same_state)
            self.session.add(
                InvoiceLine(
                    invoice_id=invoice.id,
                    product_id=product.id,
                    description=product.product_name,
                    hsn_code=product.hsn_code,
                    quantity=line.quantity,
                    unit_price=line.unit_price,
                    gst_rate=rate,
                    taxable_amount=line_taxable,
                    cgst_amount=line_cgst,
                    sgst_amount=line_sgst,
                    igst_amount=line_igst,
                )
            )
            taxable = money(taxable + line_taxable)
            cgst = money(cgst + line_cgst)
            sgst = money(sgst + line_sgst)
            igst = money(igst + line_igst)
        invoice.taxable_amount = taxable
        invoice.cgst_amount = cgst
        invoice.sgst_amount = sgst
        invoice.igst_amount = igst
        invoice.total_amount = money(taxable + cgst + sgst + igst + invoice.delivery_charge)
        self.session.add(invoice)
        await self.session.flush()
        return invoice

    async def get_invoice(self, invoice_id: UUID) -> InvoiceRead:
        invoice = await get_or_404(self.session, Invoice, invoice_id)
        return await self._read(invoice)

    async def get_for_order(self, order_id: UUID) -> InvoiceRead:
        invoice = await self.session.scalar(select(Invoice).where(Invoice.sales_order_id == order_id))
        if invoice is None:
            raise HTTPException(status_code=404, detail="Invoice not found")
        return await self._read(invoice)

    async def list_invoices(self) -> list[InvoiceRead]:
        rows = await self.session.scalars(select(Invoice).order_by(Invoice.created_at.desc()))
        return [await self._read(row) for row in rows]

    async def add_payment(self, invoice_id: UUID, data: PaymentCreate, actor: User) -> InvoiceRead:
        if data.method not in {"cash", "online"}:
            raise HTTPException(status_code=400, detail="Payment method must be cash or online")
        invoice = await get_or_404(self.session, Invoice, invoice_id)
        payment = Payment(
            invoice_id=invoice.id,
            amount=money(data.amount),
            method=data.method,
            note=data.note,
            attachment_id=data.attachment_id,
            recorded_by_user_id=actor.id,
        )
        self.session.add(payment)
        invoice.amount_paid = money(invoice.amount_paid + payment.amount)
        if invoice.amount_paid <= 0:
            invoice.status = "unpaid"
        elif invoice.amount_paid < invoice.total_amount:
            invoice.status = "partial"
        else:
            invoice.status = "paid"
        self.session.add(invoice)
        await commit_or_conflict(self.session)
        return await self._read(invoice)

    async def _next_number(self, prefix: str) -> str:
        year = financial_year()
        result = await self.session.execute(
            select(InvoiceSequence).where(InvoiceSequence.financial_year == year).with_for_update()
        )
        sequence = result.scalar_one_or_none()
        if sequence is None:
            sequence = InvoiceSequence(financial_year=year, last_number=0)
            self.session.add(sequence)
            await self.session.flush()
        sequence.last_number += 1
        self.session.add(sequence)
        await self.session.flush()
        return f"{prefix}/{year}/{sequence.last_number:04d}"

    async def _read(self, invoice: Invoice) -> InvoiceRead:
        lines = list(
            await self.session.scalars(select(InvoiceLine).where(InvoiceLine.invoice_id == invoice.id))
        )
        payments = list(
            await self.session.scalars(select(Payment).where(Payment.invoice_id == invoice.id))
        )
        return InvoiceRead.model_validate(invoice).model_copy(
            update={
                "lines": lines,
                "payments": [PaymentRead.model_validate(row) for row in payments],
                "has_pdf": invoice.pdf_attachment_id is not None,
            }
        )

    async def draft_for_order(self, order_id: UUID) -> InvoiceDraft:
        order, customer, company, lines, products = await self._order_bundle(order_id)
        invoice = await self.session.scalar(select(Invoice).where(Invoice.sales_order_id == order.id))
        drafted: list[InvoiceDraftLine] = []
        for line in lines:
            product = products[line.product_id]
            unit = await self.session.get(MeasurementUnit, product.measurement_unit_id)
            drafted.append(
                InvoiceDraftLine(
                    line_id=line.id,
                    product_name=product.product_name,
                    quantity=line.quantity,
                    unit=unit.name if unit else "Nos",
                    mrp=line.unit_price,
                    gst_percent=Decimal(product.gst_percent if product.gst else 0),
                )
            )
        return InvoiceDraft(
            customer_name=customer.name,
            customer_address=customer.address,
            customer_state=customer.state,
            customer_gst_number=customer.gst_number,
            customer_phone=customer.phone_number,
            delivery_charge=money(order.delivery_charge),
            same_state=_same_state(company.state, customer.state),
            seller_name=SELLER_NAME,
            seller_gstin=company.gstin,
            lines=drafted,
            has_pdf=bool(invoice and invoice.pdf_attachment_id),
            invoice_id=invoice.id if invoice else None,
            invoice_number=invoice.number if invoice else None,
        )

    async def issue_for_order(
        self,
        order_id: UUID,
        data: InvoiceIssue,
        actor: User,
        attachments: AttachmentService,
    ) -> InvoiceRead:
        order, customer, company, lines, products = await self._order_bundle(order_id)
        by_id = {line.id: line for line in lines}
        if {item.line_id for item in data.lines} != set(by_id):
            raise HTTPException(status_code=400, detail="Set the MRP and GST for every line on the order")
        invoice = await self.session.scalar(select(Invoice).where(Invoice.sales_order_id == order.id))
        if invoice is not None and invoice.pdf_attachment_id is not None:
            raise HTTPException(status_code=409, detail="This order already has an invoice")
        same_state = _same_state(company.state, customer.state)
        if invoice is None:
            invoice = Invoice(
                sales_order_id=order.id,
                customer_id=customer.id,
                number=await self._next_number(company.invoice_prefix),
                same_state=same_state,
                delivery_charge=money(order.delivery_charge),
            )
            self.session.add(invoice)
            await self.session.flush()
        else:
            await self.session.execute(delete(InvoiceLine).where(InvoiceLine.invoice_id == invoice.id))
            invoice.same_state = same_state
            invoice.delivery_charge = money(order.delivery_charge)
        taxable = money(0)
        cgst = money(0)
        sgst = money(0)
        igst = money(0)
        bill_lines: list[BillLine] = []
        for item in data.lines:
            line = by_id[item.line_id]
            product = products[line.product_id]
            unit = await self.session.get(MeasurementUnit, product.measurement_unit_id)
            rate = money(item.mrp)
            line_taxable = money(line.quantity * rate)
            line_cgst, line_sgst, line_igst = split_gst(item.gst_percent, line_taxable, same_state=same_state)
            line.unit_price = rate
            self.session.add(line)
            self.session.add(
                InvoiceLine(
                    invoice_id=invoice.id,
                    product_id=product.id,
                    description=product.product_name,
                    hsn_code=product.hsn_code,
                    quantity=qty(line.quantity),
                    unit_price=rate,
                    gst_rate=money(item.gst_percent),
                    taxable_amount=line_taxable,
                    cgst_amount=line_cgst,
                    sgst_amount=line_sgst,
                    igst_amount=line_igst,
                )
            )
            taxable = money(taxable + line_taxable)
            cgst = money(cgst + line_cgst)
            sgst = money(sgst + line_sgst)
            igst = money(igst + line_igst)
            bill_lines.append(
                BillLine(
                    description=product.product_name,
                    quantity=line.quantity,
                    rate=rate,
                    unit=unit.name if unit else "Nos",
                    gst_percent=money(item.gst_percent),
                    amount=line_taxable,
                )
            )
        invoice.taxable_amount = taxable
        invoice.cgst_amount = cgst
        invoice.sgst_amount = sgst
        invoice.igst_amount = igst
        invoice.total_amount = money(taxable + cgst + sgst + igst + invoice.delivery_charge)
        if invoice.amount_paid <= 0:
            invoice.status = "unpaid"
        elif invoice.amount_paid < invoice.total_amount:
            invoice.status = "partial"
        else:
            invoice.status = "paid"
        self.session.add(invoice)
        await self.session.flush()
        previous = await self._outstanding(customer.id, exclude=invoice.id)
        current = money(previous + invoice.total_amount - invoice.amount_paid)
        payload = render_invoice_pdf(
            Bill(
                number=invoice.number,
                dated=_bill_date(invoice.created_at),
                buyer_name=customer.name,
                buyer_address=customer.address,
                buyer_state=customer.state,
                buyer_gstin=customer.gst_number or "",
                buyer_phone=customer.phone_number,
                order_ref=str(order.id).split("-")[0].upper(),
                notes=order.notes or "",
                lines=bill_lines,
                taxable=invoice.taxable_amount,
                cgst=invoice.cgst_amount,
                sgst=invoice.sgst_amount,
                igst=invoice.igst_amount,
                delivery=invoice.delivery_charge,
                total=invoice.total_amount,
                same_state=invoice.same_state,
                previous_balance=previous,
                current_balance=current,
                seller_gstin=company.gstin,
                seller_address=company.address,
                seller_state=company.state,
            )
        )
        filename = f"{SELLER_NAME}-{invoice.number.replace('/', '-')}.pdf"
        stored = await attachments.store_bytes(
            self.session,
            filename=filename,
            content_type="application/pdf",
            payload=payload,
            actor=actor,
        )
        invoice.pdf_attachment_id = stored.id
        self.session.add(invoice)
        await commit_or_conflict(self.session)
        return await self._read(invoice)

    async def pdf_file(self, invoice_id: UUID, attachments: AttachmentService) -> tuple[bytes, str]:
        invoice = await get_or_404(self.session, Invoice, invoice_id)
        if invoice.pdf_attachment_id is None:
            raise HTTPException(status_code=404, detail="This invoice has no PDF yet")
        stored = await get_or_404(self.session, Attachment, invoice.pdf_attachment_id)
        return await attachments.read_bytes(stored.object_key), stored.filename

    async def _order_bundle(
        self, order_id: UUID
    ) -> tuple[SalesOrder, Customer, CompanySettings, list[SalesOrderLine], dict[UUID, Product]]:
        order = await get_or_404(self.session, SalesOrder, order_id)
        if order.status != "dispatched":
            raise HTTPException(status_code=400, detail="Dispatch the order before creating the invoice")
        customer = await get_or_404(self.session, Customer, order.customer_id)
        company = await self.session.scalar(select(CompanySettings))
        if company is None:
            raise HTTPException(status_code=400, detail="Company settings are missing")
        lines = list(
            await self.session.scalars(select(SalesOrderLine).where(SalesOrderLine.sales_order_id == order.id))
        )
        products: dict[UUID, Product] = {}
        for line in lines:
            product = await self.session.get(Product, line.product_id)
            if product is None:
                raise HTTPException(status_code=404, detail="A product on this order no longer exists")
            products[product.id] = product
        return order, customer, company, lines, products

    async def _outstanding(self, customer_id: UUID, *, exclude: UUID) -> Decimal:
        rows = await self.session.scalars(
            select(Invoice).where(
                Invoice.customer_id == customer_id,
                Invoice.id != exclude,
                Invoice.pdf_attachment_id.is_not(None),
            )
        )
        total = money(0)
        for row in rows:
            total = money(total + row.total_amount - row.amount_paid)
        return total


def _bill_date(moment: datetime) -> str:
    current = moment if moment.tzinfo else moment.replace(tzinfo=timezone.utc)
    local = current.astimezone(ZoneInfo(auth_settings.APP_TIMEZONE))
    return f"{local.day:02d}-{_MONTHS[local.month - 1]}-{str(local.year)[-2:]}"


def _same_state(company_state: str, customer_state: str) -> bool:
    left = company_state.strip().lower()
    right = customer_state.strip().lower()
    if not left or not right:
        return True
    return left == right
