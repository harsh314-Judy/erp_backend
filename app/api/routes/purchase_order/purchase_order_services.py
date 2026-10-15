from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.api.routes.user.user_model import User
from app.db.repository import commit_or_conflict

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

        rows = await self.session.scalars(select(PurchaseOrder).order_by(PurchaseOrder.created_at.desc()))
        return [await self._read(row, show_prices=show_prices, staff_view=staff_view) for row in rows]

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

        await get_or_404(self.session, Supplier, data["supplier_id"])
        order = PurchaseOrder(
            supplier_id=data["supplier_id"],
            notes=data.get("notes"),
            expected_vehicle_plate=data.get("expected_vehicle_plate"),
            created_by_user_id=actor.id,
            status="ordered",
        )
        self.session.add(order)
        await self.session.flush()
        for line in data["lines"]:
            if bool(line.get("product_id")) == bool(line.get("raw_material_id")):
                raise HTTPException(status_code=400, detail="Each line needs a product or a raw material")
            self.session.add(
                PurchaseOrderLine(
                    purchase_order_id=order.id,
                    product_id=line.get("product_id"),
                    raw_material_id=line.get("raw_material_id"),
                    quantity=Decimal(str(line["quantity"])),
                    unit_price=Decimal(str(line["unit_price"])),
                )
            )
        request_ids = data.get("request_ids") or []
        if request_ids:
            from app.api.routes.purchase_order.purchase_order_model import PurchaseRequest

            requests = await self.session.scalars(
                select(PurchaseRequest).where(PurchaseRequest.id.in_(request_ids))  # type: ignore[attr-defined]
            )
            for request in requests:
                request.status = "converted"
                request.purchase_order_id = order.id
                self.session.add(request)
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
        from app.api.routes.inventory.inventory_services import InventoryService
        from app.api.routes.product.product_model import Product
        from app.api.routes.purchase_order.purchase_order_model import PurchaseOrder, PurchaseOrderLine
        from app.api.routes.raw_material.raw_material_model import RawMaterial

        order = await get_or_404(self.session, PurchaseOrder, order_id)
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
                note="Purchase verified",
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
        order.status = "verified"
        self.session.add(order)
        await commit_or_conflict(self.session)
        return await self._read(order, show_prices=True, staff_view=False)

    async def _read(self, order, *, show_prices: bool, staff_view: bool) -> dict:
        from app.api.routes.purchase_order.purchase_order_model import PurchaseOrderLine
        from app.api.routes.supplier.supplier_model import Supplier

        supplier = await self.session.get(Supplier, order.supplier_id)
        lines = list(
            await self.session.scalars(
                select(PurchaseOrderLine).where(PurchaseOrderLine.purchase_order_id == order.id)
            )
        )
        return {
            "id": order.id,
            "supplier_id": None if staff_view else order.supplier_id,
            "supplier_name": None if staff_view else (supplier.supplier_company_name if supplier else None),
            "notes": order.notes,
            "status": order.status,
            "expected_vehicle_plate": order.expected_vehicle_plate,
            "arrived_vehicle_plate": order.arrived_vehicle_plate,
            "plate_mismatch_note": order.plate_mismatch_note,
            "receipt_attachment_id": order.receipt_attachment_id,
            "lines": [
                {
                    "id": line.id,
                    "product_id": line.product_id,
                    "raw_material_id": line.raw_material_id,
                    "quantity": line.quantity,
                    "unit_price": line.unit_price if show_prices and not staff_view else None,
                }
                for line in lines
            ],
        }
