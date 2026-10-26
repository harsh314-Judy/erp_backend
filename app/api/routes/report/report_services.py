from decimal import Decimal

from sqlalchemy import func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.api.routes.inventory.inventory_services import InventoryService
from app.api.routes.invoice.gst import money
from app.api.routes.invoice.invoice_model import Invoice, InvoiceLine
from app.api.routes.product.product_model import Product
from app.api.routes.production.production_model import ProductionJob, ProductionJobStage
from app.api.routes.purchase_order.purchase_order_model import PurchaseOrder
from app.api.routes.raw_material.raw_material_model import RawMaterial
from app.api.routes.report.report_schemas import (
    DashboardRead,
    LowStockItem,
    ProductionReport,
    SalesReport,
)
from app.api.routes.sales.sales_model import SalesOrder
from app.api.routes.user.user_model import Role, User
from app.api.security.permissions import VIEW_FINANCIALS, role_has


class ReportService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def sales_report(self, actor: User) -> SalesReport:
        orders = list(await self.session.scalars(select(SalesOrder)))
        pending = sum(1 for order in orders if order.status == "open")
        report = SalesReport(total_orders=len(orders), pending_orders=pending)
        role = await self.session.get(Role, actor.role_id)
        if not role_has(role.role_name if role else None, VIEW_FINANCIALS):
            return report
        invoices = list(await self.session.scalars(select(Invoice)))
        total = money(0)
        gst = money(0)
        non_gst = money(0)
        for invoice in invoices:
            total = money(total + invoice.total_amount)
            tax = invoice.cgst_amount + invoice.sgst_amount + invoice.igst_amount
            if tax > 0:
                gst = money(gst + invoice.total_amount)
            else:
                non_gst = money(non_gst + invoice.total_amount)
        report.total_sales = total
        report.gst_sales = gst
        report.non_gst_sales = non_gst
        return report

    async def production_report(self) -> ProductionReport:
        rows = list(await self.session.scalars(select(ProductionJob)))
        return ProductionReport(
            total_jobs=len(rows),
            completed_jobs=sum(1 for row in rows if row.status == "completed"),
            jobs_in_progress=sum(1 for row in rows if row.status == "in_progress"),
            pending_jobs=sum(1 for row in rows if row.status == "pending"),
        )

    async def inventory_rows(self) -> list[dict]:
        inventory = InventoryService(self.session)
        items: list[dict] = []
        for product in await self.session.scalars(select(Product).order_by(Product.product_name)):
            snapshot = await inventory.stock_snapshot(product)
            items.append({"kind": "product", "id": product.id, "name": product.product_name, **snapshot})
        for material in await self.session.scalars(select(RawMaterial).order_by(RawMaterial.name)):
            snapshot = await inventory.material_snapshot(material)
            items.append({"kind": "raw_material", "id": material.id, "name": material.name, **snapshot})
        return items

    async def dashboard(self, actor: User) -> DashboardRead:
        role = await self.session.get(Role, actor.role_id)
        role_name = role.role_name if role else "staff"
        shortages: list[LowStockItem] = []
        for product in await self.session.scalars(select(Product).order_by(Product.product_name)):
            if product.quantity < product.alert_quantity:
                shortages.append(
                    LowStockItem(
                        kind="product",
                        id=product.id,
                        name=product.product_name,
                        on_hand=product.quantity,
                        minimum=product.alert_quantity,
                        product_type=product.product_type,
                    )
                )
        for material in await self.session.scalars(select(RawMaterial).order_by(RawMaterial.name)):
            if material.quantity < material.alert_quantity:
                shortages.append(
                    LowStockItem(
                        kind="raw_material",
                        id=material.id,
                        name=material.name,
                        on_hand=material.quantity,
                        minimum=material.alert_quantity,
                    )
                )
        approvals = int(
            await self.session.scalar(
                select(func.count()).select_from(ProductionJob).where(ProductionJob.status == "awaiting_approval")
            )
            or 0
        )
        unpaid = int(
            await self.session.scalar(
                select(func.count()).select_from(Invoice).where(Invoice.status != "paid")
            )
            or 0
        )
        my_jobs = int(
            await self.session.scalar(
                select(func.count())
                .select_from(ProductionJobStage)
                .where(ProductionJobStage.assigned_user_id == actor.id, ProductionJobStage.status == "active")
            )
            or 0
        )
        incoming = int(
            await self.session.scalar(
                select(func.count())
                .select_from(PurchaseOrder)
                .where(PurchaseOrder.status.in_(["ordered", "arrived"]))  # type: ignore[attr-defined]
            )
            or 0
        )
        sales = await self.sales_report(actor) if role_name != "staff" else None
        production = await self.production_report() if role_name != "staff" else None
        return DashboardRead(
            role_name=role_name,
            sales=sales,
            production=production,
            low_stock=len(shortages),
            low_stock_items=shortages,
            approvals=approvals,
            unpaid_invoices=unpaid,
            my_jobs=my_jobs,
            incoming_shipments=incoming,
        )
