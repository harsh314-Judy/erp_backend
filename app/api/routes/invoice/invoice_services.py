from decimal import Decimal
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.api.routes.customer.customer_model import Customer
from app.api.routes.invoice.gst import financial_year, money, split_gst
from app.api.routes.invoice.invoice_model import Invoice, InvoiceLine, InvoiceSequence, Payment
from app.api.routes.invoice.invoice_schemas import InvoiceRead, PaymentCreate, PaymentRead
from app.api.routes.product.product_model import Product
from app.api.routes.sales.sales_model import SalesOrder, SalesOrderLine
from app.api.routes.settings.settings_model import CompanySettings
from app.api.routes.user.user_model import User
from app.db.repository import commit_or_conflict, get_or_404


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
            }
        )


def _same_state(company_state: str, customer_state: str) -> bool:
    left = company_state.strip().lower()
    right = customer_state.strip().lower()
    if not left or not right:
        return True
    return left == right
