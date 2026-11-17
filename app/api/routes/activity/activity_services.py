import re
from datetime import datetime, time, timezone
from decimal import Decimal
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.api.routes.activity.activity_model import ActivityEvent
from app.api.routes.activity.activity_schemas import ActivityRead
from app.db.base import utcnow

_PAYMENT = re.compile(r"payment\s+([0-9]+(?:\.[0-9]+)?)\s+by\s+(\S+)", re.IGNORECASE)
_FIGURE = re.compile(r"\d[\d,]*(?:\.\d+)?")


async def record_activity(
    session: AsyncSession,
    *,
    kind: str,
    summary: str,
    ref_type: str,
    ref_id: UUID | None,
    actor_id: UUID | None,
    link: str | None,
    occurred_at: datetime | None = None,
) -> None:
    session.add(
        ActivityEvent(
            occurred_at=occurred_at or utcnow(),
            kind=kind,
            summary=summary[:2000],
            ref_type=ref_type,
            ref_id=ref_id,
            actor_user_id=actor_id,
            link=link,
        )
    )


def _bound(value: datetime, end: bool) -> datetime:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    if end and value.hour == 0 and value.minute == 0 and value.second == 0:
        return datetime.combine(value.date(), time(23, 59, 59), tzinfo=value.tzinfo)
    return value


async def list_activity(
    session: AsyncSession, *, start: datetime, end: datetime, kind: str | None
) -> list[ActivityEvent]:
    query = select(ActivityEvent).where(
        ActivityEvent.occurred_at >= _bound(start, False),
        ActivityEvent.occurred_at <= _bound(end, True),
    )
    if kind:
        query = query.where(ActivityEvent.kind == kind)
    query = query.order_by(ActivityEvent.occurred_at.desc())
    return list(await session.scalars(query))


def _plain(value: Decimal | int | str) -> str:
    text = format(Decimal(str(value)), "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text or "0"


def _figure(value: Decimal | int | str, hide: bool) -> str:
    text = _plain(value)
    if not hide:
        return text
    digits = [char for char in text if char.isdigit()]
    if len(digits) <= 1:
        return digits[0] if digits else text
    return f"{digits[0]}xxx"


def _mask(text: str) -> str:
    def repl(match: re.Match[str]) -> str:
        digits = [char for char in match.group(0) if char.isdigit()]
        if len(digits) <= 1:
            return digits[0] if digits else match.group(0)
        return f"{digits[0]}xxx"

    return _FIGURE.sub(repl, text)


def _code(value: UUID) -> str:
    return str(value)[:8].upper()


def _person(user) -> str:
    if user is None:
        return ""
    return " ".join(part for part in (user.first_name, user.last_name) if part).strip()


def _changed(left: Decimal, right: Decimal) -> bool:
    return abs(left - right) > Decimal("0.0005")


async def _map(session: AsyncSession, model, ids: set[UUID]) -> dict:
    if not ids:
        return {}
    rows = list(await session.scalars(select(model).where(model.id.in_(ids))))  # type: ignore[attr-defined]
    return {row.id: row for row in rows}


async def present_activity(session: AsyncSession, rows: list[ActivityEvent], *, hide_figures: bool) -> list[ActivityRead]:
    from app.api.routes.attendance.attendance_model import Attendance
    from app.api.routes.customer.customer_model import Customer
    from app.api.routes.floor.floor_model import FloorEntry, FloorEntryWorker
    from app.api.routes.invoice.invoice_model import Invoice
    from app.api.routes.operation.operation_model import Operation
    from app.api.routes.product.product_model import Product
    from app.api.routes.production.production_model import ProductionJob, ProductionJobInput
    from app.api.routes.purchase_order.purchase_order_model import PurchaseOrder, PurchaseOrderLine
    from app.api.routes.raw_material.raw_material_model import RawMaterial
    from app.api.routes.sales.sales_model import SalesOrder, SalesOrderLine
    from app.api.routes.supplier.supplier_model import Supplier
    from app.api.routes.user.user_model import User

    def ids(ref_type: str) -> set[UUID]:
        return {row.ref_id for row in rows if row.ref_type == ref_type and row.ref_id is not None}

    sales = await _map(session, SalesOrder, ids("sales_order"))
    jobs = await _map(session, ProductionJob, ids("production_job"))
    invoices = await _map(session, Invoice, ids("invoice"))
    purchases = await _map(session, PurchaseOrder, ids("purchase_order"))
    floors = await _map(session, FloorEntry, ids("floor_entry"))
    attendance = await _map(session, Attendance, ids("attendance"))
    user_ids = {row.actor_user_id for row in rows if row.actor_user_id is not None}
    user_ids.update(mark.user_id for mark in attendance.values() if mark.user_id)
    user_ids.update(entry.created_by_user_id for entry in floors.values() if entry.created_by_user_id)
    users = await _map(session, User, user_ids)

    customer_ids = {order.customer_id for order in sales.values()}
    customer_ids.update(invoice.customer_id for invoice in invoices.values())
    customers = await _map(session, Customer, customer_ids)
    suppliers = await _map(session, Supplier, {order.supplier_id for order in purchases.values()})
    products = await _map(session, Product, {job.product_id for job in jobs.values()})
    operations = await _map(session, Operation, {entry.operation_id for entry in floors.values()})

    sales_ids = set(sales)
    sale_lines = list(await session.scalars(select(SalesOrderLine).where(SalesOrderLine.sales_order_id.in_(sales_ids)))) if sales_ids else []
    sale_invoices = list(await session.scalars(select(Invoice).where(Invoice.sales_order_id.in_(sales_ids)))) if sales_ids else []
    invoice_by_order = {row.sales_order_id: row for row in sale_invoices}
    extra_products = {line.product_id for line in sale_lines}
    extra_products.update(entry.output_product_id for entry in floors.values() if entry.output_product_id)
    products.update(await _map(session, Product, extra_products - set(products)))

    job_ids = set(jobs)
    job_inputs = list(await session.scalars(select(ProductionJobInput).where(ProductionJobInput.job_id.in_(job_ids)))) if job_ids else []
    material_ids = {item.raw_material_id for item in job_inputs if item.raw_material_id}
    input_products = {item.product_id for item in job_inputs if item.product_id}
    purchase_ids = set(purchases)
    purchase_lines = list(
        await session.scalars(select(PurchaseOrderLine).where(PurchaseOrderLine.purchase_order_id.in_(purchase_ids)))
    ) if purchase_ids else []
    material_ids.update(line.raw_material_id for line in purchase_lines if line.raw_material_id)
    input_products.update(line.product_id for line in purchase_lines if line.product_id)
    materials = await _map(session, RawMaterial, material_ids)
    products.update(await _map(session, Product, input_products - set(products)))

    floor_ids = set(floors)
    workers = list(await session.scalars(select(FloorEntryWorker).where(FloorEntryWorker.entry_id.in_(floor_ids)))) if floor_ids else []
    workers_by_entry: dict[UUID, list[str]] = {}
    for worker in workers:
        workers_by_entry.setdefault(worker.entry_id, []).append(worker.worker_name)

    def item_name(product_id: UUID | None, material_id: UUID | None) -> str:
        if material_id and material_id in materials:
            return materials[material_id].name
        if product_id and product_id in products:
            return products[product_id].product_name
        return "Item"

    def sales_title(row: ActivityEvent) -> str | None:
        order = sales.get(row.ref_id)
        if order is None:
            return None
        customer = customers.get(order.customer_id)
        names = [item_name(line.product_id, None) for line in sale_lines if line.sales_order_id == order.id]
        invoice = invoice_by_order.get(order.id)
        value = invoice.total_amount if invoice is not None else sum((line.quantity * line.unit_price for line in sale_lines if line.sales_order_id == order.id), Decimal("0"))
        who = customer.name if customer else "Sales order"
        goods = ", ".join(dict.fromkeys(names)) or "goods"
        return f"{who} · {_code(order.id)} · {_figure(value, hide_figures)} · {goods}"

    def job_title(row: ActivityEvent) -> str | None:
        job = jobs.get(row.ref_id)
        if job is None:
            return None
        product = products.get(job.product_id)
        approver = _person(users.get(row.actor_user_id)) if row.actor_user_id else ""
        if not approver:
            for event in reversed((job.operation_flow or {}).get("log") or []):
                if event.get("action") == "approved" and event.get("user_name"):
                    approver = str(event["user_name"])
                    break
        changes: list[str] = []
        for item in job_inputs:
            if item.job_id != job.id:
                continue
            name = item_name(item.product_id, item.raw_material_id)
            if item.actual_quantity is not None and _changed(item.actual_quantity, item.planned_quantity):
                changes.append(f"{name} {_figure(item.planned_quantity, hide_figures)} to {_figure(item.actual_quantity, hide_figures)}")
            elif item.wastage_quantity and item.wastage_quantity > 0:
                changes.append(f"{name} scrap {_figure(item.wastage_quantity, hide_figures)}")
        material = ", ".join(changes) if changes else "no material change"
        made = product.product_name if product else "Job"
        return f"{made} · approved by {approver or 'an approver'} · produced {_figure(job.produced_quantity, hide_figures)} · {material}"

    def payment_title(row: ActivityEvent, party: str) -> str:
        match = _PAYMENT.search(row.summary or "")
        amount = _figure(match.group(1), hide_figures) if match else ""
        method = match.group(2) if match else ""
        bits = [party]
        if amount:
            bits.append(amount)
        if method:
            bits.append(method)
        return " · ".join(bits)

    def purchase_title(row: ActivityEvent) -> str | None:
        order = purchases.get(row.ref_id)
        if order is None:
            return None
        supplier = suppliers.get(order.supplier_id)
        company = supplier.supplier_company_name if supplier else "Supplier"
        if row.kind == "payments":
            return payment_title(row, company)
        names = [item_name(line.product_id, line.raw_material_id) for line in purchase_lines if line.purchase_order_id == order.id]
        goods = ", ".join(dict.fromkeys(names)) or "goods"
        return f"Received {goods} from {company}"

    def floor_title(row: ActivityEvent) -> str | None:
        entry = floors.get(row.ref_id)
        if entry is None:
            return None
        operation = operations.get(entry.operation_id)
        department = operation.name.replace("_", " ").replace("-", " ").title() if operation else "the floor"
        people = ", ".join(workers_by_entry.get(entry.id, []))
        if not people:
            people = _person(users.get(entry.created_by_user_id))
        made = entry.output_name or "goods"
        amount = f"{_figure(entry.output_quantity, hide_figures)} {entry.output_unit}".strip()
        bits = [bit for bit in (people, made, amount, department) if bit]
        return " · ".join(bits)

    def attendance_title(row: ActivityEvent) -> str | None:
        mark = attendance.get(row.ref_id)
        if mark is None:
            return None
        name = _person(users.get(mark.user_id)) if mark.user_id else ""
        verb = "signed out" if "signed out" in (row.summary or "") else "signed in"
        return f"{name or mark.person} {verb}"

    presented: list[ActivityRead] = []
    for row in rows:
        summary = None
        if row.ref_type == "sales_order":
            summary = sales_title(row)
        elif row.ref_type == "production_job":
            summary = job_title(row)
        elif row.ref_type == "invoice":
            invoice = invoices.get(row.ref_id)
            customer = customers.get(invoice.customer_id) if invoice else None
            party = customer.name if customer else "Customer"
            number = invoice.number if invoice else ""
            summary = payment_title(row, f"{party} · {number}" if number else party)
        elif row.ref_type == "purchase_order":
            summary = purchase_title(row)
        elif row.ref_type == "floor_entry":
            summary = floor_title(row)
        elif row.ref_type == "attendance":
            summary = attendance_title(row)
        text = summary or row.summary
        if hide_figures and summary is None:
            text = _mask(text)
        presented.append(
            ActivityRead(
                id=row.id,
                occurred_at=row.occurred_at,
                kind=row.kind,
                summary=text,
                ref_type=row.ref_type,
                ref_id=row.ref_id,
                link=row.link,
            )
        )
    return presented
