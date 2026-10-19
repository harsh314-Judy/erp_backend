from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.api.routes.inventory.inventory_model import (
    InventoryMovement,
    StockRequest,
    StockReservation,
)
from app.api.routes.invoice.gst import qty
from app.api.routes.notification.notification_services import notify
from app.api.routes.product.product_model import Product
from app.api.routes.production.production_model import ProductionJob
from app.api.routes.raw_material.raw_material_model import RawMaterial
from app.api.routes.user.user_model import User
from app.db.repository import commit_or_conflict, get_or_404


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class InventoryService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def lock_product(self, product_id: UUID) -> Product:
        result = await self.session.execute(
            select(Product).where(Product.id == product_id).with_for_update()
        )
        row = result.scalar_one_or_none()
        if row is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")
        return row

    async def lock_material(self, material_id: UUID) -> RawMaterial:
        result = await self.session.execute(
            select(RawMaterial).where(RawMaterial.id == material_id).with_for_update()
        )
        row = result.scalar_one_or_none()
        if row is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Raw material not found")
        return row

    async def held_map(
        self, *, product_ids: list[UUID] | None = None, raw_material_ids: list[UUID] | None = None
    ) -> dict[UUID, Decimal]:
        field = StockReservation.product_id if product_ids is not None else StockReservation.raw_material_id
        ids = product_ids if product_ids is not None else raw_material_ids or []
        if not ids:
            return {}
        result = await self.session.execute(
            select(field, func.coalesce(func.sum(StockReservation.quantity), 0))
            .where(StockReservation.status == "held", field.in_(ids))  # type: ignore[union-attr]
            .group_by(field)
        )
        return {item_id: qty(total) for item_id, total in result.all() if item_id is not None}

    async def making_counts(self, product_ids: list[UUID]) -> dict[UUID, int]:
        if not product_ids:
            return {}
        result = await self.session.execute(
            select(ProductionJob.product_id, func.count())
            .where(
                ProductionJob.product_id.in_(product_ids),  # type: ignore[attr-defined]
                ProductionJob.status.in_(["pending", "in_progress", "awaiting_approval"]),  # type: ignore[attr-defined]
            )
            .group_by(ProductionJob.product_id)
        )
        return {product_id: int(count) for product_id, count in result.all()}

    async def held(
        self, *, product_id: UUID | None = None, raw_material_id: UUID | None = None
    ) -> Decimal:
        query = select(func.coalesce(func.sum(StockReservation.quantity), 0)).where(
            StockReservation.status == "held"
        )
        if product_id is not None:
            query = query.where(StockReservation.product_id == product_id)
        if raw_material_id is not None:
            query = query.where(StockReservation.raw_material_id == raw_material_id)
        total = await self.session.scalar(query)
        return qty(total or 0)

    async def available_product(self, product: Product) -> Decimal:
        free = qty(product.quantity) - await self.held(product_id=product.id)
        return qty(max(free, Decimal("0")))

    async def available_material(self, material: RawMaterial) -> Decimal:
        free = qty(material.quantity) - await self.held(raw_material_id=material.id)
        return qty(max(free, Decimal("0")))

    async def hold(
        self,
        *,
        quantity: Decimal,
        source_type: str,
        source_id: UUID,
        product_id: UUID | None = None,
        raw_material_id: UUID | None = None,
    ) -> StockReservation:
        amount = qty(quantity)
        if amount <= 0:
            raise HTTPException(status_code=400, detail="Hold quantity must be greater than zero")
        if product_id is not None:
            item = await self.lock_product(product_id)
            free = await self.available_product(item)
        elif raw_material_id is not None:
            item = await self.lock_material(raw_material_id)
            free = await self.available_material(item)
        else:
            raise HTTPException(status_code=400, detail="Choose a product or a raw material")
        if free < amount:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Not enough free stock to hold",
            )
        row = StockReservation(
            product_id=product_id,
            raw_material_id=raw_material_id,
            quantity=amount,
            status="held",
            source_type=source_type,
            source_id=source_id,
        )
        self.session.add(row)
        await self.session.flush()
        return row

    async def release(self, reservation_id: UUID) -> None:
        row = await self.session.get(StockReservation, reservation_id)
        if row is None or row.status != "held":
            return
        row.status = "released"
        self.session.add(row)
        await self.session.flush()

    async def consume(
        self,
        reservation_id: UUID,
        actual: Decimal,
        *,
        user_id: UUID | None,
        source_type: str,
        source_id: UUID,
        note: str | None = None,
    ) -> None:
        row = await self.session.get(StockReservation, reservation_id)
        if row is None or row.status != "held":
            raise HTTPException(status_code=409, detail="This stock hold is no longer active")
        used = qty(actual)
        if used < 0 or used > qty(row.quantity):
            raise HTTPException(status_code=400, detail="Used quantity is outside the held amount")
        if row.product_id is not None:
            item = await self.lock_product(row.product_id)
        else:
            item = await self.lock_material(row.raw_material_id)  # type: ignore[arg-type]
        if used > 0:
            item.quantity = qty(qty(item.quantity) - used)
            self.session.add(item)
            await self._move(
                product_id=row.product_id,
                raw_material_id=row.raw_material_id,
                quantity=-used,
                reason="consume",
                source_type=source_type,
                source_id=source_id,
                user_id=user_id,
                note=note,
            )
            await self._alert_if_low(item, user_id)
        row.status = "consumed"
        self.session.add(row)
        await self.session.flush()

    async def receive(
        self,
        *,
        quantity: Decimal,
        reason: str,
        source_type: str,
        source_id: UUID | None,
        user_id: UUID | None,
        note: str | None = None,
        product_id: UUID | None = None,
        raw_material_id: UUID | None = None,
    ) -> None:
        amount = qty(quantity)
        if amount == 0:
            return
        if product_id is not None:
            item = await self.lock_product(product_id)
        elif raw_material_id is not None:
            item = await self.lock_material(raw_material_id)
        else:
            raise HTTPException(status_code=400, detail="Choose a product or a raw material")
        item.quantity = qty(qty(item.quantity) + amount)
        self.session.add(item)
        await self._move(
            product_id=product_id,
            raw_material_id=raw_material_id,
            quantity=amount,
            reason=reason,
            source_type=source_type,
            source_id=source_id,
            user_id=user_id,
            note=note,
        )
        if amount < 0:
            await self._alert_if_low(item, user_id)
        await self.session.flush()

    async def adjust(
        self,
        *,
        actor: User,
        quantity_delta: Decimal,
        reason: str,
        product_id: UUID | None = None,
        raw_material_id: UUID | None = None,
    ) -> None:
        note = reason.strip()
        if not note:
            raise HTTPException(status_code=400, detail="A reason is required")
        await self.receive(
            quantity=qty(quantity_delta),
            reason="adjustment",
            source_type="adjustment",
            source_id=None,
            user_id=actor.id,
            note=note,
            product_id=product_id,
            raw_material_id=raw_material_id,
        )
        await commit_or_conflict(self.session)

    async def request_stock(
        self,
        *,
        actor: User,
        quantity: Decimal,
        note: str | None,
        product_id: UUID | None = None,
        raw_material_id: UUID | None = None,
    ) -> StockRequest:
        amount = qty(quantity)
        if amount <= 0:
            raise HTTPException(status_code=400, detail="Request a quantity greater than zero")
        responsible_id: UUID | None = None
        label = "stock"
        if product_id is not None:
            product = await get_or_404(self.session, Product, product_id)
            responsible_id = product.responsible_user_id
            label = product.product_name
        elif raw_material_id is not None:
            material = await get_or_404(self.session, RawMaterial, raw_material_id)
            responsible_id = material.responsible_user_id
            label = material.name
        else:
            raise HTTPException(status_code=400, detail="Choose a product or a raw material")
        row = StockRequest(
            product_id=product_id,
            raw_material_id=raw_material_id,
            quantity=amount,
            note=note,
            requested_by_user_id=actor.id,
            responsible_user_id=responsible_id,
        )
        self.session.add(row)
        await self.session.flush()
        if responsible_id is not None:
            await notify(
                self.session,
                [responsible_id],
                title=f"Stock request for {label}",
                body=note or f"Please make or order {amount} more.",
                kind="stock_request",
                link="/staff",
            )
        await commit_or_conflict(self.session)
        await self.session.refresh(row)
        return row

    async def stock_snapshot(self, product: Product) -> dict:
        held = await self.held(product_id=product.id)
        on_hand = qty(product.quantity)
        making = await self.session.scalar(
            select(func.count())
            .select_from(ProductionJob)
            .where(
                ProductionJob.product_id == product.id,
                ProductionJob.status.in_(["pending", "in_progress", "awaiting_approval"]),  # type: ignore[attr-defined]
            )
        )
        return _status(on_hand, held, qty(product.alert_quantity), bool(making))

    async def material_snapshot(self, material: RawMaterial) -> dict:
        held = await self.held(raw_material_id=material.id)
        return _status(qty(material.quantity), held, qty(material.alert_quantity), False)

    async def list_movements(
        self,
        *,
        product_id: UUID | None,
        raw_material_id: UUID | None,
        user_id: UUID | None,
        limit: int = 100,
    ) -> list[InventoryMovement]:
        query = select(InventoryMovement).order_by(InventoryMovement.created_at.desc()).limit(limit)
        if product_id is not None:
            query = query.where(InventoryMovement.product_id == product_id)
        if raw_material_id is not None:
            query = query.where(InventoryMovement.raw_material_id == raw_material_id)
        if user_id is not None:
            query = query.where(InventoryMovement.user_id == user_id)
        result = await self.session.scalars(query)
        return list(result)

    async def _move(self, **kwargs) -> None:
        self.session.add(InventoryMovement(**kwargs))

    async def _alert_if_low(self, item: Product | RawMaterial, actor_id: UUID | None) -> None:
        if qty(item.quantity) >= qty(item.alert_quantity):
            return
        responsible = getattr(item, "responsible_user_id", None)
        if responsible is None or responsible == actor_id:
            targets = [responsible] if responsible else []
        else:
            targets = [responsible]
        if not targets:
            return
        name = item.product_name if isinstance(item, Product) else item.name
        await notify(
            self.session,
            targets,
            title=f"{name} is below its minimum",
            body=f"On hand is {qty(item.quantity)}. Minimum is {qty(item.alert_quantity)}.",
            kind="low_stock",
            link="/products" if isinstance(item, Product) else "/raw-materials",
        )


def _status(on_hand: Decimal, held: Decimal, minimum: Decimal, making: bool) -> dict:
    available = qty(max(on_hand - held, Decimal("0")))
    if making:
        label = "being_manufactured"
    elif held > 0:
        label = "in_use"
    elif on_hand < minimum:
        label = "low"
    else:
        label = "normal"
    if on_hand < minimum and label != "low":
        label = f"{label}_low"
    return {
        "on_hand": on_hand,
        "held": held,
        "available": available,
        "minimum": minimum,
        "status": label,
    }


async def users_for_operation(session: AsyncSession, operation_id: UUID) -> list[UUID]:
    from app.api.routes.operation.operation_model import UserOperation

    result = await session.scalars(
        select(UserOperation.user_id).where(UserOperation.operation_id == operation_id)
    )
    return list(result)


def movement_visible(row: InventoryMovement, *, prices: bool) -> dict:
    del prices
    return {
        "id": row.id,
        "product_id": row.product_id,
        "raw_material_id": row.raw_material_id,
        "quantity": row.quantity,
        "reason": row.reason,
        "source_type": row.source_type,
        "source_id": row.source_id,
        "user_id": row.user_id,
        "note": row.note,
        "created_at": row.created_at,
    }
