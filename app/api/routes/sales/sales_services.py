from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.api.routes.sales.sales_model import Sale
from app.api.routes.sales.sales_schemas import SaleCreate, SaleRead, SaleUpdate, SalesOrderCreate, SalesOrderRead
from app.api.routes.user.user_model import User
from app.api.schemas.pagination import PaginatedResponse, PaginationParams
from app.db.repository import (
    commit_or_conflict,
    create_model,
    delete_model,
    get_or_404,
    list_models,
    to_page,
    update_model,
)

ORDER_STATUSES = {"initiated", "process", "in_delivery", "delivered", "cancelled"}
_LEGACY_STATUS = {"open": "initiated", "dispatched": "delivered"}


def canonical_status(status: str) -> str:
    return _LEGACY_STATUS.get(status, status)


class SalesService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_sales(self, pagination: PaginationParams) -> PaginatedResponse[SaleRead]:
        rows, total = await list_models(self.session, Sale, pagination)
        return to_page([SaleRead.model_validate(row) for row in rows], total, pagination)

    async def get_sale(self, sale_id: UUID) -> SaleRead:
        return SaleRead.model_validate(await get_or_404(self.session, Sale, sale_id))

    async def create_sale(self, data: SaleCreate) -> SaleRead:
        row = await create_model(self.session, Sale, data)
        return SaleRead.model_validate(row)

    async def update_sale(self, sale_id: UUID, data: SaleUpdate) -> SaleRead:
        row = await update_model(self.session, Sale, sale_id, data)
        return SaleRead.model_validate(row)

    async def delete_sale(self, sale_id: UUID) -> None:
        await delete_model(self.session, Sale, sale_id)


class SalesOrderService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_orders(self, *, show_prices: bool) -> list[SalesOrderRead]:
        import json

        from sqlalchemy import text

        from app.api.routes.sales.sales_schemas import SalesOrderLineRead

        rows = (
            await self.session.execute(
                text(
                    """
                    SELECT
                      o.id,
                      o.customer_id,
                      c.name AS customer_name,
                      o.notes,
                      o.status,
                      o.packaging_user_id,
                      nullif(btrim(concat(u.first_name, ' ', coalesce(u.last_name, ''))), '') AS packaging_name,
                      o.delivery_charge,
                      coalesce((
                        SELECT json_agg(json_build_object(
                          'id', l.id,
                          'product_id', l.product_id,
                          'product_name', p.product_name,
                          'quantity', l.quantity::text,
                          'held_quantity', l.held_quantity::text,
                          'unit_price', l.unit_price::text,
                          'shortfall_choice', l.shortfall_choice
                        ) ORDER BY l.created_at)
                        FROM sales_order_lines l
                        LEFT JOIN products p ON p.id = l.product_id
                        WHERE l.sales_order_id = o.id
                      ), '[]'::json) AS lines,
                      i.id AS invoice_id,
                      (i.pdf_attachment_id IS NOT NULL) AS invoice_has_pdf,
                      o.updated_at
                    FROM sales_orders o
                    LEFT JOIN customers c ON c.id = o.customer_id
                    LEFT JOIN users u ON u.id = o.packaging_user_id
                    LEFT JOIN invoices i ON i.sales_order_id = o.id
                    ORDER BY o.created_at DESC
                    """
                )
            )
        ).mappings().all()
        rendered: list[SalesOrderRead] = []
        for row in rows:
            lines = row["lines"]
            if isinstance(lines, str):
                lines = json.loads(lines)
            rendered.append(
                SalesOrderRead(
                    id=row["id"],
                    customer_id=row["customer_id"],
                    customer_name=row["customer_name"],
                    notes=row["notes"],
                    status=canonical_status(row["status"]),
                    packaging_user_id=row["packaging_user_id"],
                    packaging_name=row["packaging_name"],
                    delivery_charge=row["delivery_charge"] if show_prices else 0,
                    lines=[
                        SalesOrderLineRead(
                            id=line["id"],
                            product_id=line["product_id"],
                            product_name=line["product_name"],
                            quantity=line["quantity"],
                            held_quantity=line["held_quantity"],
                            unit_price=line["unit_price"] if show_prices else None,
                            shortfall_choice=line["shortfall_choice"],
                        )
                        for line in lines or []
                    ],
                    invoice_id=row["invoice_id"],
                    invoice_has_pdf=bool(row["invoice_has_pdf"]),
                    updated_at=row["updated_at"],
                )
            )
        return rendered

    async def delete_dispatched(self) -> int:
        from sqlalchemy import delete

        from app.api.routes.invoice.invoice_model import Invoice, InvoiceLine, Payment
        from app.api.routes.sales.sales_model import SalesOrder

        order_ids = list(
            await self.session.scalars(
                select(SalesOrder.id).where(SalesOrder.status.in_(("dispatched", "delivered")))
            )
        )
        if not order_ids:
            return 0
        invoice_ids = list(
            await self.session.scalars(select(Invoice.id).where(Invoice.sales_order_id.in_(order_ids)))
        )
        if invoice_ids:
            await self.session.execute(delete(Payment).where(Payment.invoice_id.in_(invoice_ids)))
            await self.session.execute(delete(InvoiceLine).where(InvoiceLine.invoice_id.in_(invoice_ids)))
            await self.session.execute(delete(Invoice).where(Invoice.id.in_(invoice_ids)))
        await self.session.execute(delete(SalesOrder).where(SalesOrder.id.in_(order_ids)))
        await commit_or_conflict(self.session)
        return len(order_ids)

    async def get_order(self, order_id: UUID, *, show_prices: bool) -> SalesOrderRead:
        from app.api.routes.sales.sales_model import SalesOrder

        return await self._read(await get_or_404(self.session, SalesOrder, order_id), show_prices)

    async def create_order(self, data: SalesOrderCreate, actor: User, *, show_prices: bool) -> SalesOrderRead:
        from app.api.routes.customer.customer_model import Customer
        from app.api.routes.invoice.gst import claim, qty
        from app.api.routes.notification.notification_services import notify
        from app.api.routes.operation.operation_model import Operation
        from app.api.routes.production.production_schemas import ProductionJobCreate
        from app.api.routes.production.production_services import ProductionService
        from app.api.routes.purchase_order.purchase_order_model import PurchaseRequest
        from app.api.routes.sales.sales_model import SalesOrder, SalesOrderLine
        from app.api.routes.settings.settings_model import CompanySettings
        from app.api.routes.inventory.inventory_services import InventoryService, users_for_operation

        customer = await get_or_404(self.session, Customer, data.customer_id)
        company = await self.session.scalar(select(CompanySettings))
        if company is None:
            raise HTTPException(status_code=400, detail="Company settings are missing")
        packaging_user_id = data.packaging_user_id
        if packaging_user_id is None:
            packaging = await self.session.scalar(select(Operation).where(Operation.name == "packaging"))
            if packaging is not None:
                managers = await users_for_operation(self.session, packaging.id)
                packaging_user_id = managers[0] if managers else None
        order = SalesOrder(
            customer_id=customer.id,
            notes=data.notes,
            status="initiated",
            packaging_user_id=packaging_user_id,
            created_by_user_id=actor.id,
            delivery_charge=company.delivery_charge,
        )
        self.session.add(order)
        await self.session.flush()
        inventory = InventoryService(self.session)
        for item in data.lines:
            product = await inventory.lock_product(item.product_id)
            free = await inventory.available_product(product)
            held, shortfall = claim(free, item.quantity)
            if shortfall > 0 and product.product_type == "both" and item.shortfall_choice not in {"make", "buy"}:
                raise HTTPException(
                    status_code=400,
                    detail=f"Choose make or buy for the shortfall of {product.product_name}",
                )
            line = SalesOrderLine(
                sales_order_id=order.id,
                product_id=product.id,
                quantity=qty(item.quantity),
                held_quantity=held,
                unit_price=product.sale_price_without_gst,
                shortfall_choice=item.shortfall_choice,
            )
            self.session.add(line)
            await self.session.flush()
            if held > 0:
                reservation = await inventory.hold(
                    quantity=held,
                    source_type="sales_order_line",
                    source_id=line.id,
                    product_id=product.id,
                )
                line.reservation_id = reservation.id
                self.session.add(line)
            if shortfall > 0:
                choice = item.shortfall_choice
                make = product.product_type == "manufactured" or (
                    product.product_type == "both" and choice == "make"
                )
                if make:
                    await ProductionService(self.session).create_job(
                        ProductionJobCreate(
                            product_id=product.id,
                            quantity=shortfall,
                            estimated_minutes=60,
                            notes=f"Shortfall for sales order {order.id}",
                            source="sales_shortfall",
                            source_id=order.id,
                        ),
                        actor,
                        commit=False,
                    )
                else:
                    self.session.add(
                        PurchaseRequest(
                            product_id=product.id,
                            quantity=shortfall,
                            source="sales_shortfall",
                            source_id=order.id,
                        )
                    )
        if packaging_user_id is not None:
            await notify(
                self.session,
                [packaging_user_id],
                title="A sales order needs packaging",
                body=customer.name,
                kind="packaging",
                link="/staff",
            )
        await commit_or_conflict(self.session)
        return await self._read(order, show_prices)

    async def assign_packaging(self, order_id: UUID, user_id: UUID, *, show_prices: bool) -> SalesOrderRead:
        from app.api.routes.notification.notification_services import notify
        from app.api.routes.sales.sales_model import SalesOrder

        order = await get_or_404(self.session, SalesOrder, order_id)
        order.packaging_user_id = user_id
        self.session.add(order)
        await notify(
            self.session,
            [user_id],
            title="A packaging task was assigned to you",
            body="Open staff work to see the order.",
            kind="packaging",
            link="/staff",
        )
        await commit_or_conflict(self.session)
        return await self._read(order, show_prices)

    async def set_status(
        self, order_id: UUID, status: str, actor: User, *, show_prices: bool
    ) -> SalesOrderRead:
        from app.api.routes.sales.sales_model import SalesOrder

        order = await get_or_404(self.session, SalesOrder, order_id)
        current = canonical_status(order.status)
        target = canonical_status(status.strip().lower().replace(" ", "_"))
        if target not in ORDER_STATUSES:
            raise HTTPException(
                status_code=400,
                detail="Status must be initiated, process, in delivery, delivered, or cancelled",
            )
        if current == target:
            return await self._read(order, show_prices)
        if current in {"delivered", "cancelled"}:
            raise HTTPException(status_code=409, detail="This order can no longer change status")
        if target == "delivered" and current != "in_delivery":
            raise HTTPException(status_code=409, detail="Mark the order in delivery before dispatching it")
        if target == "cancelled":
            await self._release_holds(order)
        elif target == "delivered":
            await self._consume_holds(order, actor)
        order.status = target
        self.session.add(order)
        await commit_or_conflict(self.session)
        return await self._read(order, show_prices)

    async def dispatch(self, order_id: UUID, actor: User, *, show_prices: bool) -> SalesOrderRead:
        return await self.set_status(order_id, "delivered", actor, show_prices=show_prices)

    async def _release_holds(self, order) -> None:
        from app.api.routes.inventory.inventory_services import InventoryService
        from app.api.routes.sales.sales_model import SalesOrderLine

        lines = list(
            await self.session.scalars(
                select(SalesOrderLine).where(SalesOrderLine.sales_order_id == order.id)
            )
        )
        inventory = InventoryService(self.session)
        for line in lines:
            if line.reservation_id is not None:
                await inventory.release(line.reservation_id)

    async def _consume_holds(self, order, actor: User) -> None:
        from app.api.routes.inventory.inventory_services import InventoryService
        from app.api.routes.sales.sales_model import SalesOrderLine

        lines = list(
            await self.session.scalars(
                select(SalesOrderLine).where(SalesOrderLine.sales_order_id == order.id)
            )
        )
        inventory = InventoryService(self.session)
        for line in lines:
            if line.reservation_id is None or line.held_quantity <= 0:
                continue
            await inventory.consume(
                line.reservation_id,
                line.held_quantity,
                user_id=actor.id,
                source_type="sales_order",
                source_id=order.id,
                note="Dispatched",
            )

    async def _read(self, order, show_prices: bool) -> SalesOrderRead:
        from app.api.routes.customer.customer_model import Customer
        from app.api.routes.invoice.invoice_model import Invoice
        from app.api.routes.product.product_model import Product
        from app.api.routes.sales.sales_model import SalesOrderLine
        from app.api.routes.sales.sales_schemas import SalesOrderLineRead, SalesOrderRead

        from app.api.routes.user.user_model import User

        customer = await self.session.get(Customer, order.customer_id)
        packer = (
            await self.session.get(User, order.packaging_user_id) if order.packaging_user_id else None
        )
        packaging_name = (
            " ".join(part for part in (packer.first_name, packer.last_name) if part) if packer else None
        )
        lines = list(
            await self.session.scalars(
                select(SalesOrderLine).where(SalesOrderLine.sales_order_id == order.id)
            )
        )
        invoice = await self.session.scalar(select(Invoice).where(Invoice.sales_order_id == order.id))
        rendered = []
        for line in lines:
            product = await self.session.get(Product, line.product_id)
            rendered.append(
                SalesOrderLineRead(
                    id=line.id,
                    product_id=line.product_id,
                    product_name=product.product_name if product else None,
                    quantity=line.quantity,
                    held_quantity=line.held_quantity,
                    unit_price=line.unit_price if show_prices else None,
                    shortfall_choice=line.shortfall_choice,
                )
            )
        return SalesOrderRead(
            id=order.id,
            customer_id=order.customer_id,
            customer_name=customer.name if customer else None,
            notes=order.notes,
            status=canonical_status(order.status),
            packaging_user_id=order.packaging_user_id,
            packaging_name=packaging_name or None,
            delivery_charge=order.delivery_charge if show_prices else 0,
            lines=rendered,
            invoice_id=invoice.id if invoice else None,
            invoice_has_pdf=bool(invoice and invoice.pdf_attachment_id),
            updated_at=order.updated_at,
        )
