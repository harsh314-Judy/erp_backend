import csv
import io
import json
from datetime import datetime
from zoneinfo import ZoneInfo

from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.routes.inventory.inventory_services import _status
from app.api.routes.invoice.gst import qty
from app.api.routes.report.report_schemas import (
    DashboardRead,
    DepartmentYield,
    LateJob,
    LowStockItem,
    MachineDown,
    ProductionReport,
    SalesReport,
    ShopReport,
)
from app.api.routes.user.user_model import Role, User
from app.api.security.permissions import VIEW_FINANCIALS, role_has


_IST = ZoneInfo("Asia/Kolkata")


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

    async def ca_csv(self, month: str) -> tuple[str, str]:
        try:
            start = datetime.strptime(month, "%Y-%m").replace(tzinfo=_IST)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="Month must be YYYY-MM") from exc
        if start.month == 12:
            end = start.replace(year=start.year + 1, month=1)
        else:
            end = start.replace(month=start.month + 1)
        rows = (
            await self.session.execute(
                text(
                    """
                    SELECT i.number, i.created_at, c.name AS customer_name, c.gst_number, c.state,
                           i.taxable_amount, i.cgst_amount, i.sgst_amount, i.igst_amount,
                           i.total_amount, i.amount_paid, i.status
                    FROM invoices i
                    JOIN customers c ON c.id = i.customer_id
                    WHERE i.created_at >= :start AND i.created_at < :end
                    ORDER BY i.created_at
                    """
                ),
                {"start": start, "end": end},
            )
        ).mappings().all()
        buffer = io.StringIO()
        writer = csv.writer(buffer)
        writer.writerow([
            "invoice_number", "invoice_date", "customer_name", "gstin", "state",
            "taxable_amount", "cgst", "sgst", "igst", "total", "amount_paid", "balance", "payment_status",
        ])
        for row in rows:
            total = row["total_amount"] or 0
            paid = row["amount_paid"] or 0
            balance = total - paid
            status = row["status"] or "unpaid"
            if status not in {"paid", "partial", "unpaid"}:
                status = "paid" if balance <= 0 else "partial" if paid else "unpaid"
            created = row["created_at"]
            local = created.astimezone(_IST).date().isoformat() if created else ""
            writer.writerow([
                row["number"], local, row["customer_name"], row["gst_number"] or "", row["state"] or "",
                total, row["cgst_amount"], row["sgst_amount"], row["igst_amount"], total, paid, balance, status,
            ])
        return buffer.getvalue(), f"ca-{month}.csv"

    async def dashboard(self, actor: User) -> DashboardRead:
        row = (
            await self.session.execute(
                text(
                    """
                    SELECT
                      coalesce((SELECT role_name FROM roles WHERE id = :role_id), 'staff') AS role_name,
                      (SELECT count(*) FROM production_jobs WHERE status = 'awaiting_approval') AS approvals,
                      (SELECT count(*) FROM invoices WHERE status <> 'paid') AS unpaid,
                      (SELECT coalesce(sum(total_amount - amount_paid), 0) FROM invoices WHERE status <> 'paid') AS unpaid_amount,
                      (SELECT count(*) FROM production_jobs
                        WHERE due_at < now()
                          AND status IN ('pending', 'in_progress', 'awaiting_approval')) AS late_jobs,
                      (SELECT count(*) FROM production_job_stages s
                        JOIN production_jobs j ON j.id = s.job_id
                        WHERE s.problem_reason IS NOT NULL
                          AND j.status IN ('pending', 'in_progress', 'awaiting_approval')) AS open_problems,
                      (SELECT count(*) FROM production_job_stages
                        WHERE assigned_user_id = :user_id AND status = 'active') AS my_jobs,
                      (SELECT count(*) FROM purchase_orders
                        WHERE status IN ('initiated', 'process', 'in_delivery')
                          AND stock_received = false) AS incoming,
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
                          'name', m.name,
                          'operation_name', o.name
                        ) ORDER BY o.name, m.name)
                        FROM machines m
                        JOIN operations o ON o.id = m.operation_id
                        WHERE m.status = 'down'
                      ), '[]'::json) AS machines_down,
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
            unpaid_amount=row.unpaid_amount if role_has(role_name, VIEW_FINANCIALS) else None,
            late_jobs=int(row.late_jobs or 0),
            open_problems=int(row.open_problems or 0),
            machines_down=[
                MachineDown(name=item["name"], operation_name=item["operation_name"])
                for item in _json_list(row.machines_down)
                if item.get("name") and item.get("operation_name")
            ],
            my_jobs=int(row.my_jobs or 0),
            incoming_shipments=int(row.incoming or 0),
        )

    async def shop_report(self, actor: User) -> ShopReport:
        role = await self.session.get(Role, actor.role_id)
        role_name = role.role_name if role else ""
        yield_rows = (
            await self.session.execute(
                text(
                    """
                    SELECT o.name AS name,
                           coalesce(sum(f.output_quantity), 0) AS good,
                           coalesce(sum(f.scrap_quantity), 0) AS scrap
                    FROM floor_entries f
                    JOIN operations o ON o.id = f.operation_id
                    WHERE f.entry_date >= ((now() AT TIME ZONE 'Asia/Kolkata')::date - 6)
                    GROUP BY o.name
                    ORDER BY o.name
                    """
                )
            )
        ).mappings().all()
        late_rows = (
            await self.session.execute(
                text(
                    """
                    SELECT j.id, p.product_name, j.due_at, j.status, o.name AS current_operation_name
                    FROM production_jobs j
                    LEFT JOIN products p ON p.id = j.product_id
                    LEFT JOIN operations o ON o.id = j.current_operation_id
                    WHERE j.due_at < now()
                      AND j.status IN ('pending', 'in_progress', 'awaiting_approval')
                    ORDER BY j.due_at
                    """
                )
            )
        ).mappings().all()
        money = (
            await self.session.execute(
                text(
                    """
                    SELECT count(*) AS unpaid_count,
                           coalesce(sum(total_amount - amount_paid), 0) AS unpaid_total
                    FROM invoices
                    WHERE status <> 'paid'
                    """
                )
            )
        ).one()
        show_money = role_has(role_name, VIEW_FINANCIALS)
        return ShopReport(
            yields=[
                DepartmentYield(name=row["name"], good=row["good"], scrap=row["scrap"])
                for row in yield_rows
            ],
            late_jobs=[
                LateJob(
                    id=row["id"],
                    product_name=row["product_name"],
                    due_at=row["due_at"],
                    status=row["status"],
                    current_operation_name=row["current_operation_name"],
                )
                for row in late_rows
            ],
            unpaid_count=int(money.unpaid_count or 0),
            unpaid_total=money.unpaid_total if show_money else None,
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
