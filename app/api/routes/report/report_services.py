import json

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.routes.inventory.inventory_services import _status
from app.api.routes.invoice.gst import qty
from app.api.routes.report.report_schemas import (
    DashboardRead,
    LowStockItem,
    ProductionReport,
    SalesReport,
)
from app.api.routes.user.user_model import Role, User
from app.api.security.permissions import VIEW_FINANCIALS, role_has


class ReportService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def sales_report(self, actor: User) -> SalesReport:
        role = await self.session.get(Role, actor.role_id)
        row = (
            await self.session.execute(
                text(
                    """
                    SELECT
                      (SELECT count(*) FROM sales_orders) AS total_orders,
                      (SELECT count(*) FROM sales_orders WHERE status IN ('open', 'initiated', 'process', 'in_delivery')) AS pending_orders,
                      (SELECT coalesce(sum(total_amount), 0) FROM invoices) AS total_sales,
                      (SELECT coalesce(sum(total_amount), 0) FROM invoices
                        WHERE cgst_amount + sgst_amount + igst_amount > 0) AS gst_sales,
                      (SELECT coalesce(sum(total_amount), 0) FROM invoices
                        WHERE cgst_amount + sgst_amount + igst_amount <= 0) AS non_gst_sales
                    """
                )
            )
        ).one()
        report = SalesReport(total_orders=int(row.total_orders), pending_orders=int(row.pending_orders))
        if not role_has(role.role_name if role else None, VIEW_FINANCIALS):
            return report
        report.total_sales = row.total_sales
        report.gst_sales = row.gst_sales
        report.non_gst_sales = row.non_gst_sales
        return report

    async def production_report(self) -> ProductionReport:
        row = (
            await self.session.execute(
                text(
                    """
                    SELECT
                      count(*) AS total_jobs,
                      count(*) FILTER (WHERE status = 'completed') AS completed_jobs,
                      count(*) FILTER (WHERE status = 'in_progress') AS jobs_in_progress,
                      count(*) FILTER (WHERE status = 'pending') AS pending_jobs
                    FROM production_jobs
                    """
                )
            )
        ).one()
        return ProductionReport(
            total_jobs=int(row.total_jobs),
            completed_jobs=int(row.completed_jobs),
            jobs_in_progress=int(row.jobs_in_progress),
            pending_jobs=int(row.pending_jobs),
        )

    async def inventory_rows(self) -> list[dict]:
        row = (
            await self.session.execute(
                text(
                    """
                    SELECT
                      coalesce((
                        SELECT json_agg(json_build_object(
                          'id', id, 'name', product_name,
                          'quantity', quantity::text, 'alert', alert_quantity::text
                        ) ORDER BY product_name)
                        FROM products
                      ), '[]'::json) AS products,
                      coalesce((
                        SELECT json_agg(json_build_object(
                          'id', id, 'name', name,
                          'quantity', quantity::text, 'alert', alert_quantity::text
                        ) ORDER BY name)
                        FROM raw_materials
                      ), '[]'::json) AS materials,
                      coalesce((
                        SELECT json_object_agg(product_id::text, total::text)
                        FROM (
                          SELECT product_id, sum(quantity) AS total
                          FROM stock_reservations
                          WHERE status = 'held' AND product_id IS NOT NULL
                          GROUP BY product_id
                        ) held_products
                      ), '{}'::json) AS held_products,
                      coalesce((
                        SELECT json_object_agg(raw_material_id::text, total::text)
                        FROM (
                          SELECT raw_material_id, sum(quantity) AS total
                          FROM stock_reservations
                          WHERE status = 'held' AND raw_material_id IS NOT NULL
                          GROUP BY raw_material_id
                        ) held_materials
                      ), '{}'::json) AS held_materials,
                      coalesce((
                        SELECT json_object_agg(product_id::text, total)
                        FROM (
                          SELECT product_id, count(*) AS total
                          FROM production_jobs
                          WHERE status IN ('pending', 'in_progress', 'awaiting_approval')
                          GROUP BY product_id
                        ) making
                      ), '{}'::json) AS making
                    """
                )
            )
        ).one()
        held_products = _json_map(row.held_products)
        held_materials = _json_map(row.held_materials)
        making = _json_map(row.making)
        items: list[dict] = []
        for product in _json_list(row.products):
            snapshot = _status(
                qty(product["quantity"]),
                qty(held_products.get(str(product["id"]), 0)),
                qty(product["alert"]),
                str(product["id"]) in making,
            )
            items.append({"kind": "product", "id": product["id"], "name": product["name"], **snapshot})
        for material in _json_list(row.materials):
            snapshot = _status(
                qty(material["quantity"]),
                qty(held_materials.get(str(material["id"]), 0)),
                qty(material["alert"]),
                False,
            )
            items.append({"kind": "raw_material", "id": material["id"], "name": material["name"], **snapshot})
        return items

    async def dashboard(self, actor: User) -> DashboardRead:
        row = (
            await self.session.execute(
                text(
                    """
                    SELECT
                      coalesce((SELECT role_name FROM roles WHERE id = :role_id), 'staff') AS role_name,
                      (SELECT count(*) FROM production_jobs WHERE status = 'awaiting_approval') AS approvals,
                      (SELECT count(*) FROM invoices WHERE status <> 'paid') AS unpaid,
                      (SELECT count(*) FROM production_job_stages
                        WHERE assigned_user_id = :user_id AND status = 'active') AS my_jobs,
                      (SELECT count(*) FROM purchase_orders
                        WHERE status IN ('ordered', 'arrived')) AS incoming,
                      (SELECT count(*) FROM sales_orders) AS total_orders,
                      (SELECT count(*) FROM sales_orders WHERE status IN ('open', 'initiated', 'process', 'in_delivery')) AS pending_orders,
                      (SELECT coalesce(sum(total_amount), 0) FROM invoices) AS total_sales,
                      (SELECT coalesce(sum(total_amount), 0) FROM invoices
                        WHERE cgst_amount + sgst_amount + igst_amount > 0) AS gst_sales,
                      (SELECT coalesce(sum(total_amount), 0) FROM invoices
                        WHERE cgst_amount + sgst_amount + igst_amount <= 0) AS non_gst_sales,
                      (SELECT count(*) FROM production_jobs) AS total_jobs,
                      (SELECT count(*) FILTER (WHERE status = 'completed') FROM production_jobs) AS completed_jobs,
                      (SELECT count(*) FILTER (WHERE status = 'in_progress') FROM production_jobs) AS jobs_in_progress,
                      (SELECT count(*) FILTER (WHERE status = 'pending') FROM production_jobs) AS pending_jobs,
                      coalesce((
                        SELECT json_agg(json_build_object(
                          'kind', 'product',
                          'id', id,
                          'name', product_name,
                          'on_hand', quantity::text,
                          'minimum', alert_quantity::text,
                          'product_type', product_type
                        ) ORDER BY product_name)
                        FROM products WHERE quantity < alert_quantity
                      ), '[]'::json) AS low_products,
                      coalesce((
                        SELECT json_agg(json_build_object(
                          'kind', 'raw_material',
                          'id', id,
                          'name', name,
                          'on_hand', quantity::text,
                          'minimum', alert_quantity::text
                        ) ORDER BY name)
                        FROM raw_materials WHERE quantity < alert_quantity
                      ), '[]'::json) AS low_materials
                    """
                ),
                {"role_id": actor.role_id, "user_id": actor.id},
            )
        ).one()
        role_name = row.role_name or "staff"
        shortages = [_stock_item(item) for item in _json_list(row.low_products)]
        shortages.extend(_stock_item(item) for item in _json_list(row.low_materials))
        sales = None
        production = None
        if role_name != "staff":
            sales = SalesReport(total_orders=int(row.total_orders), pending_orders=int(row.pending_orders))
            if role_has(role_name, VIEW_FINANCIALS):
                sales.total_sales = row.total_sales
                sales.gst_sales = row.gst_sales
                sales.non_gst_sales = row.non_gst_sales
            production = ProductionReport(
                total_jobs=int(row.total_jobs),
                completed_jobs=int(row.completed_jobs),
                jobs_in_progress=int(row.jobs_in_progress),
                pending_jobs=int(row.pending_jobs),
            )
        return DashboardRead(
            role_name=role_name,
            sales=sales,
            production=production,
            low_stock=len(shortages),
            low_stock_items=shortages,
            approvals=int(row.approvals or 0),
            unpaid_invoices=int(row.unpaid or 0),
            my_jobs=int(row.my_jobs or 0),
            incoming_shipments=int(row.incoming or 0),
        )


def _json_list(value: object) -> list[dict]:
    if value is None:
        return []
    parsed = json.loads(value) if isinstance(value, str) else value
    if not isinstance(parsed, list):
        return []
    return [item for item in parsed if isinstance(item, dict)]


def _json_map(value: object) -> dict:
    if value is None:
        return {}
    parsed = json.loads(value) if isinstance(value, str) else value
    return parsed if isinstance(parsed, dict) else {}


def _stock_item(item: dict) -> LowStockItem:
    return LowStockItem(
        kind=str(item.get("kind") or ""),
        id=item["id"],
        name=str(item.get("name") or ""),
        on_hand=item.get("on_hand") or 0,
        minimum=item.get("minimum") or 0,
        product_type=item.get("product_type"),
    )
