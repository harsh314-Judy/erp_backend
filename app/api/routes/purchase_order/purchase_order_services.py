from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.api.routes.user.user_model import User
from app.db.repository import commit_or_conflict

ORDER_STATUSES = {"initiated", "process", "in_delivery", "delivered", "received", "accounted", "cancelled"}
SLIP_KINDS = {"dispatch_slip", "received_slip", "cargo_photo", "vehicle_plate", "supplier_invoice"}

from app.api.routes.purchase_order.purchase_order_model import (
    PurchaseOrderProduct,
    PurchaseOrderRawMaterial,
)
from app.api.routes.purchase_order.purchase_order_schemas import (
    PurchaseOrderProductCreate,
    PurchaseOrderProductRead,
    PurchaseOrderProductUpdate,
    PurchaseOrderRawMaterialCreate,
    PurchaseOrderRawMaterialRead,
    PurchaseOrderRawMaterialUpdate,
    PurchaseOrderUpdate,
)
from app.api.schemas.pagination import PaginatedResponse, PaginationParams
from app.db.repository import (
    create_model,
    delete_model,
    get_or_404,
    list_models,
    to_page,
    update_model,
)


class PurchaseOrderService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_material_orders(
        self, pagination: PaginationParams
    ) -> PaginatedResponse[PurchaseOrderRawMaterialRead]:
        rows, total = await list_models(self.session, PurchaseOrderRawMaterial, pagination)
        return to_page(
            [PurchaseOrderRawMaterialRead.model_validate(row) for row in rows],
            total,
            pagination,
        )

    async def get_material_order(self, order_id: UUID) -> PurchaseOrderRawMaterialRead:
        return PurchaseOrderRawMaterialRead.model_validate(
            await get_or_404(self.session, PurchaseOrderRawMaterial, order_id)
        )

    async def create_material_order(
        self, data: PurchaseOrderRawMaterialCreate
    ) -> PurchaseOrderRawMaterialRead:
        row = await create_model(self.session, PurchaseOrderRawMaterial, data)
        return PurchaseOrderRawMaterialRead.model_validate(row)

    async def update_material_order(
        self, order_id: UUID, data: PurchaseOrderRawMaterialUpdate
    ) -> PurchaseOrderRawMaterialRead:
        row = await update_model(self.session, PurchaseOrderRawMaterial, order_id, data)
        return PurchaseOrderRawMaterialRead.model_validate(row)

    async def delete_material_order(self, order_id: UUID) -> None:
        await delete_model(self.session, PurchaseOrderRawMaterial, order_id)

    async def list_product_orders(
        self, pagination: PaginationParams
    ) -> PaginatedResponse[PurchaseOrderProductRead]:
        rows, total = await list_models(self.session, PurchaseOrderProduct, pagination)
        return to_page(
            [PurchaseOrderProductRead.model_validate(row) for row in rows],
            total,
            pagination,
        )

    async def get_product_order(self, order_id: UUID) -> PurchaseOrderProductRead:
        return PurchaseOrderProductRead.model_validate(
            await get_or_404(self.session, PurchaseOrderProduct, order_id)
        )

    async def create_product_order(
        self, data: PurchaseOrderProductCreate
    ) -> PurchaseOrderProductRead:
        row = await create_model(self.session, PurchaseOrderProduct, data)
        return PurchaseOrderProductRead.model_validate(row)

    async def update_product_order(
        self, order_id: UUID, data: PurchaseOrderProductUpdate
    ) -> PurchaseOrderProductRead:
        row = await update_model(self.session, PurchaseOrderProduct, order_id, data)
        return PurchaseOrderProductRead.model_validate(row)

    async def delete_product_order(self, order_id: UUID) -> None:
        await delete_model(self.session, PurchaseOrderProduct, order_id)


class PurchaseFlowService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_orders(self, *, show_prices: bool, staff_view: bool) -> list[dict]:
        from app.api.routes.purchase_order.purchase_order_model import PurchaseOrder

        rows = list(
            await self.session.scalars(select(PurchaseOrder).order_by(PurchaseOrder.created_at.desc()))
        )
        return await self._read_many(rows, show_prices=show_prices, staff_view=staff_view)

    async def list_requests(self) -> list[dict]:
        from app.api.routes.purchase_order.purchase_order_model import PurchaseRequest

        rows = await self.session.scalars(
            select(PurchaseRequest).where(PurchaseRequest.status == "open")
        )
        return [
            {
                "id": row.id,
                "product_id": row.product_id,
                "raw_material_id": row.raw_material_id,
                "quantity": row.quantity,
                "source": row.source,
                "status": row.status,
            }
            for row in rows
        ]

    async def create_order(self, data: dict, actor: User) -> dict:
        from decimal import Decimal

        from app.api.routes.purchase_order.purchase_order_model import PurchaseOrder, PurchaseOrderLine
        from app.api.routes.supplier.supplier_model import Supplier

        supplier = await get_or_404(self.session, Supplier, data["supplier_id"])
        lines = data.get("lines") or []
        if not lines:
            raise HTTPException(status_code=400, detail="Add at least one item")
        mode = str(data.get("transport_mode") or "").strip().lower()
        if mode not in {"truck", "handcart", "staff_vehicle"}:
            raise HTTPException(status_code=400, detail="Choose truck, hand cart, or staff pickup")
        plate = data.get("expected_vehicle_plate")
        if isinstance(plate, str):
            plate = plate.strip().upper() or None
        driver = (data.get("driver_name") or "").strip() or None
        phone = (data.get("carrier_phone") or "").strip() or None
        pickup = data.get("pickup_user_id") or None
        if mode == "truck" and (not plate or not driver):
            raise HTTPException(status_code=400, detail="A truck needs the licence plate and the driver's name")
        if mode == "handcart" and (not driver or not phone):
            raise HTTPException(status_code=400, detail="A hand cart needs the person's name and phone")
        if mode == "staff_vehicle" and not pickup:
            raise HTTPException(status_code=400, detail="Choose the staff member who will pick this up")
        attachments = data.get("attachments") or []
        if not any(str(item.get("kind") or "") in {"supplier_invoice", "received_slip"} for item in attachments):
            raise HTTPException(status_code=400, detail="Upload the receipt photo")
        order = PurchaseOrder(
            supplier_id=supplier.id,
            notes=data.get("notes"),
            challan_number=(data.get("challan_number") or None),
            challan_note=data.get("challan_note"),
            expected_vehicle_plate=plate,
            created_by_user_id=actor.id,
            status="received",
            stock_received=False,
            transport_mode=mode,
            driver_name=driver,
            carrier_phone=phone,
            pickup_user_id=pickup,
        )
        self.session.add(order)
        await self.session.flush()
        for line in lines:
            await self._add_line(order, supplier, line)
        await self._link_files(order, attachments)
        orders = [order]
        request_ids = data.get("request_ids") or []
        if request_ids and orders:
            from app.api.routes.purchase_order.purchase_order_model import PurchaseRequest

            requests = await self.session.scalars(
                select(PurchaseRequest).where(PurchaseRequest.id.in_(request_ids))  # type: ignore[attr-defined]
            )
            for request in requests:
                request.status = "converted"
                request.purchase_order_id = orders[0].id
                self.session.add(request)
        await self.session.flush()
        await commit_or_conflict(self.session)
        return {"orders": await self._read_many(orders, show_prices=True, staff_view=False)}

    async def update_order(self, order_id: UUID, data: PurchaseOrderUpdate, actor: User) -> dict:
        from app.api.routes.purchase_order.purchase_order_model import PurchaseOrder

        order = await get_or_404(self.session, PurchaseOrder, order_id)
        changes = data.model_dump(exclude_unset=True)
        locked = order.stock_received or order.status == "cancelled"
        if "supplier_id" in changes and changes["supplier_id"] is not None:
            if locked:
                raise HTTPException(status_code=409, detail="This order can no longer be edited")
            from app.api.routes.supplier.supplier_model import Supplier

            await get_or_404(self.session, Supplier, changes["supplier_id"])
            order.supplier_id = changes["supplier_id"]
        if changes.get("lines") is not None:
            if locked:
                raise HTTPException(status_code=409, detail="This order can no longer be edited")
            await self._replace_lines(order, changes["lines"])
        if "notes" in changes:
            order.notes = changes["notes"]
        if "challan_number" in changes:
            order.challan_number = (changes["challan_number"] or "").strip() or None
        if "challan_note" in changes:
            order.challan_note = changes["challan_note"]
        if "expected_vehicle_plate" in changes:
            plate = changes["expected_vehicle_plate"]
            order.expected_vehicle_plate = plate.strip().upper() if isinstance(plate, str) and plate.strip() else None
        if "status" in changes and changes["status"] is not None:
            status = str(changes["status"]).strip().lower()
            if status not in ORDER_STATUSES:
                raise HTTPException(
                    status_code=400,
                    detail="Status must be initiated, process, in delivery, delivered, or cancelled",
                )
            if order.status == "cancelled" and status != "cancelled":
                raise HTTPException(status_code=409, detail="Restore the order before changing it")
            if status == "cancelled":
                reason = str(changes.get("cancel_reason") or "").strip()
                if not reason:
                    raise HTTPException(status_code=400, detail="A reason is required to cancel this order")
                if order.stock_received:
                    raise HTTPException(status_code=409, detail="Stock was already added for this order")
                if order.status != "cancelled":
                    order.status_before_cancel = order.status
                order.cancel_reason = reason
            if order.stock_received and status != order.status:
                raise HTTPException(status_code=409, detail="Stock was already added for this order")
            if status == "delivered" and not order.stock_received:
                await self._require_receipt_proof(order)
                await self._note_received(order, actor)
            if status == "in_delivery" and order.status != "in_delivery":
                await self._notify_purchase(order, actor, arriving=True)
            order.status = status
        self.session.add(order)
        await commit_or_conflict(self.session)
        return await self._read(order, show_prices=True, staff_view=False)

    async def account_materials(self, order_id: UUID, actor: User) -> dict:
        from app.api.routes.purchase_order.purchase_order_model import PurchaseOrder

        order = await get_or_404(self.session, PurchaseOrder, order_id)
        if order.status == "cancelled":
            raise HTTPException(status_code=409, detail="This order is cancelled")
        if order.stock_received:
            return await self._read(order, show_prices=True, staff_view=False)
        await self._require_receipt_proof(order)
        await self._apply_receipt(order, actor)
        order.stock_received = True
        order.status = "accounted"
        self.session.add(order)
        await self._note_received(order, actor)
        await commit_or_conflict(self.session)
        return await self._read(order, show_prices=True, staff_view=False)

    async def restore_order(self, order_id: UUID, actor: User) -> dict:
        del actor
        from app.api.routes.purchase_order.purchase_order_model import PurchaseOrder

        order = await get_or_404(self.session, PurchaseOrder, order_id)
        if order.status != "cancelled":
            raise HTTPException(status_code=409, detail="This order is not cancelled")
        order.status = order.status_before_cancel or "received"
        order.cancel_reason = None
        order.status_before_cancel = None
        self.session.add(order)
        await commit_or_conflict(self.session)
        return await self._read(order, show_prices=True, staff_view=False)

    async def inspect_receipt(self, order_id: UUID, data, actor: User) -> dict:
        from app.api.routes.purchase_order.purchase_order_model import PurchaseOrder

        order = await get_or_404(self.session, PurchaseOrder, order_id)
        if order.stock_received:
            raise HTTPException(status_code=409, detail="Stock was already added for this order")
        if order.status != "in_delivery":
            raise HTTPException(status_code=409, detail="Inspect the truck while it is in delivery")
        result = str(data.result or "").strip().lower()
        if result == "fail":
            reason = str(data.reason or "").strip().lower()
            if reason not in {"wrong thickness", "rust", "short count", "other"}:
                raise HTTPException(status_code=400, detail="Choose why the delivery failed")
            order.receipt_fail_reason = reason
            order.receipt_fail_note = (data.note or "").strip() or None
            self.session.add(order)
            await commit_or_conflict(self.session)
            return await self._read(order, show_prices=True, staff_view=False)
        if result != "pass":
            raise HTTPException(status_code=400, detail="Pass or fail the delivery")
        await self._require_receipt_proof(order)
        order.status = "delivered"
        order.receipt_fail_reason = None
        order.receipt_fail_note = None
        self.session.add(order)
        await self._note_received(order, actor)
        await self._notify_purchase(order, actor, arriving=False)
        await commit_or_conflict(self.session)
        return await self._read(order, show_prices=True, staff_view=False)

    async def mark_arrived(self, order_id: UUID, payload: dict) -> dict:
        from app.api.routes.purchase_order.purchase_order_model import PurchaseOrder

        order = await get_or_404(self.session, PurchaseOrder, order_id)
        if order.status not in {"ordered", "draft"}:
            raise HTTPException(status_code=409, detail="This order is not waiting to arrive")
        order.arrived_vehicle_plate = payload["arrived_vehicle_plate"].strip().upper()
        order.receipt_attachment_id = payload.get("receipt_attachment_id")
        order.status = "arrived"
        self.session.add(order)
        await commit_or_conflict(self.session)
        return await self._read(order, show_prices=True, staff_view=False)

    async def verify(self, order_id: UUID, actor: User, mismatch_note: str | None) -> dict:
        from app.api.routes.purchase_order.purchase_order_model import PurchaseOrder

        order = await get_or_404(self.session, PurchaseOrder, order_id)
        if order.stock_received:
            raise HTTPException(status_code=409, detail="Stock was already added for this order")
        if order.status != "arrived":
            raise HTTPException(status_code=409, detail="Record the arrival before verifying")
        expected = (order.expected_vehicle_plate or "").strip().upper()
        arrived = (order.arrived_vehicle_plate or "").strip().upper()
        if expected and arrived and expected != arrived and not (mismatch_note and mismatch_note.strip()):
            raise HTTPException(
                status_code=400,
                detail="The vehicle plate does not match. Add a note before verifying.",
            )
        order.plate_mismatch_note = mismatch_note
        order.status = "verified"
        self.session.add(order)
        await self._note_received(order, actor)
        await commit_or_conflict(self.session)
        return await self._read(order, show_prices=True, staff_view=False)

    async def add_attachment(self, order_id: UUID, payload: dict) -> dict:
        from app.api.routes.attachment.attachment_model import Attachment
        from app.api.routes.purchase_order.purchase_order_model import PurchaseOrder, PurchaseOrderAttachment

        order = await get_or_404(self.session, PurchaseOrder, order_id)
        kind = str(payload.get("kind") or "")
        if kind not in SLIP_KINDS:
            raise HTTPException(status_code=400, detail="That photo kind is not recognised")
        stored = await self.session.get(Attachment, payload.get("attachment_id"))
        if stored is None:
            raise HTTPException(status_code=400, detail="That file was not uploaded")
        link = PurchaseOrderAttachment(purchase_order_id=order.id, attachment_id=stored.id, kind=kind)
        self.session.add(link)
        await commit_or_conflict(self.session)
        return await self._read(order, show_prices=True, staff_view=False)

    async def add_payment(self, order_id: UUID, data, actor: User) -> dict:
        from decimal import Decimal

        from app.api.routes.activity.activity_services import record_activity
        from app.api.routes.attachment.attachment_model import Attachment
        from app.api.routes.purchase_order.purchase_order_model import (
            PurchaseOrder,
            PurchaseOrderLine,
            PurchasePayment,
        )

        if data.method not in {"cash", "upi", "bank"}:
            raise HTTPException(status_code=400, detail="Payment method must be cash, upi, or bank")
        if data.attachment_id is None:
            raise HTTPException(status_code=400, detail="A photo of the payment is required")
        order = await get_or_404(self.session, PurchaseOrder, order_id)
        if order.status == "cancelled":
            raise HTTPException(status_code=409, detail="This order is cancelled")
        stored = await self.session.get(Attachment, data.attachment_id)
        if stored is None:
            raise HTTPException(status_code=400, detail="Payment photo was not found")
        lines = list(
            await self.session.scalars(
                select(PurchaseOrderLine).where(PurchaseOrderLine.purchase_order_id == order.id)
            )
        )
        total = sum((line.quantity * line.unit_price for line in lines), Decimal("0"))
        amount = Decimal(str(data.amount)).quantize(Decimal("0.01"))
        if order.amount_paid + amount > total + Decimal("0.009"):
            raise HTTPException(status_code=400, detail="That installment is more than the amount still due")
        self.session.add(
            PurchasePayment(
                purchase_order_id=order.id,
                amount=amount,
                method=data.method,
                note=data.note,
                attachment_id=data.attachment_id,
                recorded_by_user_id=actor.id,
            )
        )
        order.amount_paid = (order.amount_paid + amount).quantize(Decimal("0.01"))
        if not order.stock_received:
            await self._require_receipt_proof(order)
            await self._apply_receipt(order, actor)
            order.stock_received = True
            order.status = "accounted"
            await self._note_received(order, actor)
        self.session.add(order)
        await record_activity(
            self.session,
            kind="payments",
            summary=f"Supplier payment {amount} by {data.method}",
            ref_type="purchase_order",
            ref_id=order.id,
            actor_id=actor.id,
            link="/accountant/payments",
        )
        await commit_or_conflict(self.session)
        return await self._read(order, show_prices=True, staff_view=False)

    async def _note_received(self, order, actor: User) -> None:
        from app.api.routes.activity.activity_services import record_activity
        from app.api.routes.supplier.supplier_model import Supplier

        supplier = await self.session.get(Supplier, order.supplier_id)
        company = supplier.supplier_company_name if supplier else "Supplier"
        await record_activity(
            self.session,
            kind="purchases",
            summary=f"Received goods from {company}",
            ref_type="purchase_order",
            ref_id=order.id,
            actor_id=actor.id,
            link="/purchases",
        )

    async def remove_attachment(self, order_id: UUID, link_id: UUID) -> dict:
        from app.api.routes.purchase_order.purchase_order_model import PurchaseOrder, PurchaseOrderAttachment

        order = await get_or_404(self.session, PurchaseOrder, order_id)
        if order.stock_received:
            raise HTTPException(status_code=409, detail="Stock was already added for this order")
        link = await get_or_404(self.session, PurchaseOrderAttachment, link_id)
        if link.purchase_order_id != order.id:
            raise HTTPException(status_code=404, detail="That file is not on this order")
        await self.session.delete(link)
        await commit_or_conflict(self.session)
        return await self._read(order, show_prices=True, staff_view=False)

    async def _link_files(self, order, attachments: list) -> None:
        from app.api.routes.attachment.attachment_model import Attachment
        from app.api.routes.purchase_order.purchase_order_model import PurchaseOrderAttachment

        for item in attachments:
            kind = str(item.get("kind") or "")
            if kind not in SLIP_KINDS:
                raise HTTPException(status_code=400, detail="That photo kind is not recognised")
            stored = await self.session.get(Attachment, item.get("attachment_id"))
            if stored is None:
                raise HTTPException(status_code=400, detail="That file was not uploaded")
            self.session.add(
                PurchaseOrderAttachment(purchase_order_id=order.id, attachment_id=stored.id, kind=kind)
            )

    async def _require_receipt_proof(self, order) -> None:
        from app.api.routes.purchase_order.purchase_order_model import PurchaseOrderAttachment

        rows = list(
            await self.session.scalars(
                select(PurchaseOrderAttachment).where(PurchaseOrderAttachment.purchase_order_id == order.id)
            )
        )
        kinds = {row.kind for row in rows}
        if "supplier_invoice" not in kinds and "received_slip" not in kinds:
            raise HTTPException(status_code=400, detail="Upload the receipt photo before stocking")

    async def _notify_purchase(self, order, actor, *, arriving: bool) -> None:
        from app.api.routes.notification.notification_services import notify, user_ids_with
        from app.api.routes.supplier.supplier_model import Supplier
        from app.api.security.permissions import MANAGE_PURCHASING

        targets = await user_ids_with(self.session, MANAGE_PURCHASING, exclude=actor.id)
        supplier = await self.session.get(Supplier, order.supplier_id)
        company = supplier.supplier_company_name if supplier else "A supplier"
        await notify(
            self.session,
            targets,
            title=f"{company} is on the way" if arriving else f"{company} stock was received",
            body="A purchase is in delivery." if arriving else "The received slip was checked and stock was credited.",
            kind="purchase_incoming" if arriving else "purchase_received",
            link="/purchases",
            email=False,
        )

    async def _remember_rates(self, product_id, material_id, unit_price, selling, gst: bool, gst_percent: int, unit_id) -> None:
        from app.api.routes.product.product_model import Product
        from app.api.routes.raw_material.raw_material_model import RawMaterial

        if product_id is not None:
            product = await self.session.get(Product, product_id)
            if product is not None:
                product.last_purchase_price = unit_price
                product.gst = gst
                product.gst_percent = gst_percent
                if selling is not None:
                    product.sale_price_without_gst = selling
                if unit_id:
                    product.measurement_unit_id = unit_id
                self.session.add(product)
        if material_id is not None:
            material = await self.session.get(RawMaterial, material_id)
            if material is not None:
                material.purchase_price = unit_price
                if selling is not None:
                    material.price = selling
                if unit_id:
                    material.measurement_unit_id = unit_id
                self.session.add(material)

    async def _add_line(self, order, supplier, line) -> None:
        from decimal import Decimal

        from app.api.routes.purchase_order.purchase_order_model import PurchaseOrderLine

        product_id = line.get("product_id")
        material_id = line.get("raw_material_id")
        if bool(product_id) == bool(material_id):
            raise HTTPException(status_code=400, detail="Each line needs a product or a raw material")
        if material_id:
            if supplier.supply_kind == "products":
                raise HTTPException(status_code=400, detail="This supplier only supplies products")
            await self._require_material_link(supplier.id, material_id)
        if product_id:
            if supplier.supply_kind == "materials":
                raise HTTPException(status_code=400, detail="This supplier only supplies raw materials")
            await self._require_product_link(supplier.id, product_id)
        purchase_rate = Decimal(str(line.get("purchase_rate") if line.get("purchase_rate") is not None else line.get("unit_price") or 0))
        gst = bool(line.get("gst"))
        gst_percent = int(line.get("gst_percent") or 0)
        unit_price = purchase_rate
        if gst and gst_percent:
            unit_price = (purchase_rate * (Decimal(100) + Decimal(gst_percent)) / Decimal(100)).quantize(Decimal("0.01"))
        selling_rate = line.get("selling_rate")
        selling = Decimal(str(selling_rate)) if selling_rate is not None and selling_rate != "" else None
        unit_id = line.get("measurement_unit_id") or None
        self.session.add(
            PurchaseOrderLine(
                purchase_order_id=order.id,
                product_id=product_id,
                raw_material_id=material_id,
                quantity=Decimal(str(line["quantity"])),
                unit_price=unit_price,
                purchase_rate=purchase_rate,
                selling_rate=selling,
                gst=gst,
                gst_percent=gst_percent if gst else 0,
                measurement_unit_id=unit_id,
            )
        )
        await self._remember_rates(product_id, material_id, unit_price, selling, gst, gst_percent if gst else 0, unit_id)

    async def _replace_lines(self, order, lines: list) -> None:
        from app.api.routes.purchase_order.purchase_order_model import PurchaseOrderLine
        from app.api.routes.supplier.supplier_model import Supplier

        if not lines:
            raise HTTPException(status_code=400, detail="Add at least one item")
        supplier = await get_or_404(self.session, Supplier, order.supplier_id)
        existing = list(
            await self.session.scalars(
                select(PurchaseOrderLine).where(PurchaseOrderLine.purchase_order_id == order.id)
            )
        )
        for line in existing:
            await self.session.delete(line)
        await self.session.flush()
        for line in lines:
            payload = line if isinstance(line, dict) else line
            if not isinstance(payload, dict):
                payload = payload.model_dump()
            await self._add_line(order, supplier, payload)

    async def _require_product_link(self, supplier_id: UUID, product_id: UUID) -> None:
        from app.api.routes.supplier.supplier_model import ProductSupplier

        link = await self.session.scalar(
            select(ProductSupplier).where(
                ProductSupplier.supplier_id == supplier_id,
                ProductSupplier.product_id == product_id,
            )
        )
        if link is None:
            raise HTTPException(status_code=400, detail="Choose a product this supplier sells")

    async def _require_material_link(self, supplier_id: UUID, raw_material_id: UUID) -> None:
        from app.api.routes.supplier.supplier_model import RawMaterialSupplier

        link = await self.session.scalar(
            select(RawMaterialSupplier).where(
                RawMaterialSupplier.supplier_id == supplier_id,
                RawMaterialSupplier.raw_material_id == raw_material_id,
            )
        )
        if link is None:
            raise HTTPException(
                status_code=400,
                detail="Choose a raw material this supplier sells",
            )

    async def _apply_receipt(self, order, actor: User) -> None:
        from app.api.routes.inventory.inventory_services import InventoryService
        from app.api.routes.product.product_model import Product
        from app.api.routes.purchase_order.purchase_order_model import PurchaseOrderLine
        from app.api.routes.raw_material.raw_material_model import RawMaterial

        inventory = InventoryService(self.session)
        lines = list(
            await self.session.scalars(
                select(PurchaseOrderLine).where(PurchaseOrderLine.purchase_order_id == order.id)
            )
        )
        for line in lines:
            await inventory.receive(
                quantity=line.quantity,
                reason="purchase_receive",
                source_type="purchase_order",
                source_id=order.id,
                user_id=actor.id,
                product_id=line.product_id,
                raw_material_id=line.raw_material_id,
                note="Purchase delivered",
            )
            if line.raw_material_id is not None:
                material = await self.session.get(RawMaterial, line.raw_material_id)
                if material is not None:
                    material.purchase_price = line.unit_price
                    self.session.add(material)
            if line.product_id is not None:
                product = await self.session.get(Product, line.product_id)
                if product is not None:
                    product.last_purchase_price = line.unit_price
                    self.session.add(product)

    async def _read(self, order, *, show_prices: bool, staff_view: bool) -> dict:
        rows = await self._read_many([order], show_prices=show_prices, staff_view=staff_view)
        return rows[0]

    async def _read_many(self, orders, *, show_prices: bool, staff_view: bool) -> list[dict]:
        from app.api.routes.product.product_model import Product
        from app.api.routes.purchase_order.purchase_order_model import PurchaseOrderLine, PurchasePayment
        from app.api.routes.raw_material.raw_material_model import RawMaterial
        from app.api.routes.supplier.supplier_model import Supplier

        if not orders:
            return []
        from app.api.routes.attachment.attachment_model import Attachment
        from app.api.routes.purchase_order.purchase_order_model import PurchaseOrderAttachment

        order_ids = [order.id for order in orders]
        pay_rows = list(
            await self.session.scalars(
                select(PurchasePayment).where(PurchasePayment.purchase_order_id.in_(order_ids))  # type: ignore[attr-defined]
            )
        )
        pay_grouped: dict = {order.id: [] for order in orders}
        for row in pay_rows:
            pay_grouped[row.purchase_order_id].append(
                {
                    "id": row.id,
                    "amount": row.amount,
                    "method": row.method,
                    "note": row.note,
                    "attachment_id": row.attachment_id,
                    "created_at": row.created_at,
                }
            )
        links = list(
            await self.session.scalars(
                select(PurchaseOrderAttachment).where(PurchaseOrderAttachment.purchase_order_id.in_(order_ids))  # type: ignore[attr-defined]
            )
        )
        stored = {
            row.id: row
            for row in await self.session.scalars(
                select(Attachment).where(Attachment.id.in_({link.attachment_id for link in links}))  # type: ignore[attr-defined]
            )
        } if links else {}
        files: dict = {order.id: [] for order in orders}
        for link in links:
            file = stored.get(link.attachment_id)
            files[link.purchase_order_id].append(
                {
                    "id": link.id,
                    "attachment_id": link.attachment_id,
                    "kind": link.kind,
                    "filename": file.filename if file else "file",
                    "content_type": file.content_type if file else "application/octet-stream",
                }
            )
        lines = list(
            await self.session.scalars(
                select(PurchaseOrderLine).where(PurchaseOrderLine.purchase_order_id.in_(order_ids))  # type: ignore[attr-defined]
            )
        )
        supplier_ids = {order.supplier_id for order in orders}
        material_ids = {line.raw_material_id for line in lines if line.raw_material_id}
        product_ids = {line.product_id for line in lines if line.product_id}
        suppliers = {
            row.id: row
            for row in await self.session.scalars(select(Supplier).where(Supplier.id.in_(supplier_ids)))  # type: ignore[attr-defined]
        } if supplier_ids else {}
        materials = {
            row.id: row.name
            for row in await self.session.scalars(select(RawMaterial).where(RawMaterial.id.in_(material_ids)))  # type: ignore[attr-defined]
        } if material_ids else {}
        products = {
            row.id: (row.product_name, row.product_type)
            for row in await self.session.scalars(select(Product).where(Product.id.in_(product_ids)))  # type: ignore[attr-defined]
        } if product_ids else {}
        grouped: dict = {order.id: [] for order in orders}
        for line in lines:
            product = products.get(line.product_id) if line.product_id else None
            item_name = materials.get(line.raw_material_id) if line.raw_material_id else (product[0] if product else None)
            grouped[line.purchase_order_id].append(
                {
                    "id": line.id,
                    "product_id": line.product_id,
                    "raw_material_id": line.raw_material_id,
                    "product_type": product[1] if product else None,
                    "item_name": item_name,
                    "quantity": line.quantity,
                    "unit_price": line.unit_price if show_prices and not staff_view else None,
                    "purchase_rate": line.purchase_rate if show_prices and not staff_view else None,
                    "selling_rate": line.selling_rate if show_prices and not staff_view else None,
                    "gst": line.gst,
                    "gst_percent": line.gst_percent,
                    "measurement_unit_id": line.measurement_unit_id,
                }
            )
        presented = []
        for order in orders:
            supplier = suppliers.get(order.supplier_id)
            presented.append(
                {
                    "id": order.id,
                    "supplier_id": None if staff_view else order.supplier_id,
                    "supplier_name": None if staff_view else (supplier.supplier_company_name if supplier else None),
                    "notes": order.notes,
                    "challan_number": order.challan_number,
                    "challan_note": order.challan_note,
                    "status": order.status,
                    "stock_received": order.stock_received,
                    "receipt_fail_reason": order.receipt_fail_reason,
                    "receipt_fail_note": order.receipt_fail_note,
                    "expected_vehicle_plate": order.expected_vehicle_plate,
                    "arrived_vehicle_plate": order.arrived_vehicle_plate,
                    "transport_mode": order.transport_mode,
                    "driver_name": order.driver_name,
                    "carrier_phone": order.carrier_phone,
                    "pickup_user_id": order.pickup_user_id,
                    "cancel_reason": order.cancel_reason,
                    "status_before_cancel": order.status_before_cancel,
                    "plate_mismatch_note": order.plate_mismatch_note,
                    "receipt_attachment_id": order.receipt_attachment_id,
                    "attachments": files.get(order.id, []),
                    "lines": grouped.get(order.id, []),
                    "amount_paid": order.amount_paid if show_prices and not staff_view else "0",
                    "payments": pay_grouped.get(order.id, []) if show_prices and not staff_view else [],
                }
            )
        return presented
