from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.api.routes.sales.sales_model import Sale
from app.api.routes.sales.sales_schemas import SaleCreate, SaleRead, SaleUpdate, SalesOrderCreate, SalesOrderRead
from app.api.routes.user.user_model import User
from app.api.schemas.pagination import PaginatedResponse, PaginationParams
from app.db.repository import (
    create_model,
    delete_model,
    get_or_404,
    list_models,
    to_page,
    update_model,
)


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
        from app.api.routes.sales.sales_model import SalesOrder

        rows = await self.session.scalars(select(SalesOrder).order_by(SalesOrder.created_at.desc()))
        return [await self._read(row, show_prices) for row in rows]

    async def get_order(self, order_id: UUID, *, show_prices: bool) -> SalesOrderRead:
        from app.api.routes.sales.sales_model import SalesOrder

        return await self._read(await get_or_404(self.session, SalesOrder, order_id), show_prices)

    async def create_order(self, data: SalesOrderCreate, actor: User, *, show_prices: bool) -> SalesOrderRead:
        from app.api.routes.customer.customer_model import Customer
        from app.api.routes.invoice.gst import claim, qty
        from app.api.routes.invoice.invoice_services import InvoiceService
        from app.api.routes.notification.notification_services import notify
        from app.api.routes.operation.operation_model import Operation
        from app.api.routes.product.product_model import Product
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
            packaging_user_id=packaging_user_id,
            created_by_user_id=actor.id,
            delivery_charge=company.delivery_charge,
        )
        self.session.add(order)
        await self.session.flush()
        inventory = InventoryService(self.session)
        products: dict[UUID, Product] = {}
        stored: list[SalesOrderLine] = []
        for item in data.lines:
            product = await inventory.lock_product(item.product_id)
            products[product.id] = product
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
            stored.append(line)
        await InvoiceService(self.session).create_for_order(order, stored, customer, products, company)
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

    async def dispatch(self, order_id: UUID, actor: User, *, show_prices: bool) -> SalesOrderRead:
        from app.api.routes.inventory.inventory_services import InventoryService
        from app.api.routes.sales.sales_model import SalesOrder, SalesOrderLine

        order = await get_or_404(self.session, SalesOrder, order_id)
        if order.status != "open":
            raise HTTPException(status_code=409, detail="This order is not open")
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
        order.status = "dispatched"
        self.session.add(order)
        await commit_or_conflict(self.session)
        return await self._read(order, show_prices)

    async def _read(self, order, show_prices: bool) -> SalesOrderRead:
        from app.api.routes.customer.customer_model import Customer
        from app.api.routes.invoice.invoice_model import Invoice
        from app.api.routes.product.product_model import Product
        from app.api.routes.sales.sales_model import SalesOrderLine
        from app.api.routes.sales.sales_schemas import SalesOrderLineRead, SalesOrderRead

        customer = await self.session.get(Customer, order.customer_id)
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
            status=order.status,
            packaging_user_id=order.packaging_user_id,
            delivery_charge=order.delivery_charge if show_prices else 0,
            lines=rendered,
            invoice_id=invoice.id if invoice else None,
        )
