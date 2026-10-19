from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.api.routes.user.user_model import User
from app.db.repository import commit_or_conflict

ORDER_STATUSES = {"initiated", "process", "in_delivery", "delivered", "cancelled"}

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
        status = str(data.get("status") or "initiated").strip().lower()
        if status not in ORDER_STATUSES:
            raise HTTPException(
                status_code=400,
                detail="Status must be initiated, process, in delivery, or delivered",
            )
        lines = data.get("lines") or []
        if not lines:
            raise HTTPException(status_code=400, detail="Add at least one item")
        plate = data.get("expected_vehicle_plate")
        if isinstance(plate, str):
            plate = plate.strip().upper() or None
        orders = []
        for line in lines:
            order = PurchaseOrder(
                supplier_id=supplier.id,
                notes=data.get("notes"),
                expected_vehicle_plate=plate,
                created_by_user_id=actor.id,
                status=status,
            )
            self.session.add(order)
            await self.session.flush()
            await self._add_line(order, supplier, line)
            orders.append(order)
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
        for order in orders:
            if order.status == "delivered":
                await self._apply_receipt(order, actor)
                order.stock_received = True
                self.session.add(order)
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
                raise HTTPException(status_code=409, detail="This order is cancelled")
            if status == "cancelled" and order.stock_received:
                raise HTTPException(status_code=409, detail="Stock was already added for this order")
            if order.stock_received and status != order.status:
                raise HTTPException(status_code=409, detail="Stock was already added for this order")
            if status == "delivered" and not order.stock_received:
                await self._apply_receipt(order, actor)
                order.stock_received = True
            order.status = status
        self.session.add(order)
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
        await self._apply_receipt(order, actor)
        order.stock_received = True
        order.status = "verified"
        self.session.add(order)
        await commit_or_conflict(self.session)
        return await self._read(order, show_prices=True, staff_view=False)

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
        self.session.add(
            PurchaseOrderLine(
                purchase_order_id=order.id,
                product_id=product_id,
                raw_material_id=material_id,
                quantity=Decimal(str(line["quantity"])),
                unit_price=Decimal(str(line["unit_price"])),
            )
        )

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
                payload = {
                    "product_id": line.product_id,
                    "raw_material_id": line.raw_material_id,
                    "quantity": line.quantity,
                    "unit_price": line.unit_price,
                }
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
                    material.price = line.unit_price
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
        from app.api.routes.purchase_order.purchase_order_model import PurchaseOrderLine
        from app.api.routes.raw_material.raw_material_model import RawMaterial
        from app.api.routes.supplier.supplier_model import Supplier

        if not orders:
            return []
        order_ids = [order.id for order in orders]
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
            row.id: row.product_name
            for row in await self.session.scalars(select(Product).where(Product.id.in_(product_ids)))  # type: ignore[attr-defined]
        } if product_ids else {}
        grouped: dict = {order.id: [] for order in orders}
        for line in lines:
            item_name = materials.get(line.raw_material_id) if line.raw_material_id else products.get(line.product_id)
            grouped[line.purchase_order_id].append(
                {
                    "id": line.id,
                    "product_id": line.product_id,
                    "raw_material_id": line.raw_material_id,
                    "item_name": item_name,
                    "quantity": line.quantity,
                    "unit_price": line.unit_price if show_prices and not staff_view else None,
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
                    "status": order.status,
                    "stock_received": order.stock_received,
                    "expected_vehicle_plate": order.expected_vehicle_plate,
                    "arrived_vehicle_plate": order.arrived_vehicle_plate,
                    "plate_mismatch_note": order.plate_mismatch_note,
                    "receipt_attachment_id": order.receipt_attachment_id,
                    "lines": grouped.get(order.id, []),
                }
            )
        return presented
