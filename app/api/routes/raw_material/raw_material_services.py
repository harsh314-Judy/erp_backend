from decimal import Decimal
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import func, select

from app.api.routes.inventory.inventory_services import InventoryService
from app.api.routes.raw_material.raw_material_model import RawMaterial, RawMaterialCategory
from app.api.routes.raw_material.raw_material_schemas import (
    RawMaterialCategoryCreate,
    RawMaterialCategoryRead,
    RawMaterialCreate,
    RawMaterialOption,
    RawMaterialRead,
    RawMaterialUpdate,
)
from app.api.routes.supplier.supplier_model import RawMaterialSupplier, Supplier
from app.api.schemas.pagination import PaginatedResponse, PaginationParams
from app.db.repository import (
    apply_changes,
    commit_or_conflict,
    create_model,
    delete_model,
    get_or_404,
    list_models,
    to_page,
)

_KINDS = {"sheet", "polish", "color", "other"}


class RawMaterialService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_categories(
        self, pagination: PaginationParams
    ) -> PaginatedResponse[RawMaterialCategoryRead]:
        rows, total = await list_models(self.session, RawMaterialCategory, pagination)
        return to_page(
            [RawMaterialCategoryRead.model_validate(row) for row in rows], total, pagination
        )

    async def create_category(self, data: RawMaterialCategoryCreate) -> RawMaterialCategoryRead:
        row = await create_model(self.session, RawMaterialCategory, data)
        return RawMaterialCategoryRead.model_validate(row)

    async def delete_category(self, category_id: UUID) -> None:
        await get_or_404(self.session, RawMaterialCategory, category_id)
        used = await self.session.scalar(
            select(func.count())
            .select_from(RawMaterial)
            .where(RawMaterial.category_id == category_id)
        )
        if used:
            raise HTTPException(
                status_code=409,
                detail="Remove this category from raw materials before deleting it",
            )
        await delete_model(self.session, RawMaterialCategory, category_id)

    async def list_materials(
        self, pagination: PaginationParams, *, query: str | None, show_prices: bool, brief: bool = False
    ) -> PaginatedResponse[RawMaterialRead]:
        statement = select(RawMaterial)
        count = select(func.count()).select_from(RawMaterial)
        if query:
            like = f"%{query.strip()}%"
            statement = statement.where(RawMaterial.name.ilike(like))
            count = count.where(RawMaterial.name.ilike(like))
        total = int(await self.session.scalar(count) or 0)
        rows = list(
            await self.session.scalars(
                statement.order_by(RawMaterial.name).offset(pagination.offset).limit(pagination.page_size)
            )
        )
        if brief:
            return to_page([self._priced(RawMaterialRead.model_validate(row), show_prices) for row in rows], total, pagination)
        held = await InventoryService(self.session).held_map(raw_material_ids=[row.id for row in rows])
        return to_page(
            [self._present_held(row, held.get(row.id, Decimal("0")), show_prices) for row in rows],
            total,
            pagination,
        )

    async def options(self, query: str | None) -> list[RawMaterialOption]:
        statement = select(RawMaterial).order_by(RawMaterial.name).limit(30)
        if query:
            statement = statement.where(RawMaterial.name.ilike(f"%{query.strip()}%"))
        rows = await self.session.scalars(statement)
        return [RawMaterialOption.model_validate(row) for row in rows]

    async def get_material(self, material_id: UUID, *, show_prices: bool) -> RawMaterialRead:
        return await self._present(await get_or_404(self.session, RawMaterial, material_id), show_prices)

    async def create_material(self, data: RawMaterialCreate, *, show_prices: bool) -> RawMaterialRead:
        self._kind(data.kind)
        await get_or_404(self.session, RawMaterialCategory, data.category_id)
        if data.supplier_id is not None:
            await self._assert_material_supplier(data.supplier_id)
        row = RawMaterial.model_validate(data.model_dump())
        self.session.add(row)
        await self.session.flush()
        if data.supplier_id is not None:
            await self._ensure_link(row.id, data.supplier_id)
        await commit_or_conflict(self.session)
        await self.session.refresh(row)
        return await self._present(row, show_prices)

    async def update_material(
        self, material_id: UUID, data: RawMaterialUpdate, *, show_prices: bool
    ) -> RawMaterialRead:
        row = await get_or_404(self.session, RawMaterial, material_id)
        if data.kind is not None:
            self._kind(data.kind)
        changes = data.model_dump(exclude_unset=True)
        if changes.get("category_id") is not None:
            await get_or_404(self.session, RawMaterialCategory, changes["category_id"])
        previous_supplier = row.supplier_id
        apply_changes(row, data)
        if "supplier_id" in changes:
            await self._sync_supplier_link(row.id, previous_supplier, row.supplier_id)
        self.session.add(row)
        await commit_or_conflict(self.session)
        await self.session.refresh(row)
        return await self._present(row, show_prices)

    async def delete_material(self, material_id: UUID) -> None:
        await delete_model(self.session, RawMaterial, material_id)

    async def _present(self, row: RawMaterial, show_prices: bool) -> RawMaterialRead:
        snapshot = await InventoryService(self.session).material_snapshot(row)
        return self._present_held(row, snapshot["held"], show_prices)

    def _present_held(self, row: RawMaterial, held: Decimal, show_prices: bool) -> RawMaterialRead:
        from app.api.routes.inventory.inventory_services import _status, qty

        snapshot = _status(qty(row.quantity), held, qty(row.alert_quantity), False)
        data = RawMaterialRead.model_validate(row).model_copy(
            update={
                "on_hand": snapshot["on_hand"],
                "held": snapshot["held"],
                "available": snapshot["available"],
                "stock_status": snapshot["status"],
            }
        )
        return self._priced(data, show_prices)

    @staticmethod
    def _priced(data: RawMaterialRead, show_prices: bool) -> RawMaterialRead:
        if not show_prices:
            data.price = None
            data.purchase_price = None
        return data

    async def _assert_material_supplier(self, supplier_id: UUID) -> Supplier:
        supplier = await get_or_404(self.session, Supplier, supplier_id)
        if supplier.supply_kind == "products":
            raise HTTPException(status_code=400, detail="This supplier only supplies products")
        return supplier

    async def _ensure_link(self, material_id: UUID, supplier_id: UUID) -> None:
        existing = await self.session.scalar(
            select(RawMaterialSupplier).where(
                RawMaterialSupplier.raw_material_id == material_id,
                RawMaterialSupplier.supplier_id == supplier_id,
            )
        )
        if existing is None:
            self.session.add(
                RawMaterialSupplier(raw_material_id=material_id, supplier_id=supplier_id)
            )

    async def _sync_supplier_link(
        self, material_id: UUID, previous: UUID | None, current: UUID | None
    ) -> None:
        if current is not None:
            await self._assert_material_supplier(current)
        if previous and previous != current:
            link = await self.session.scalar(
                select(RawMaterialSupplier).where(
                    RawMaterialSupplier.raw_material_id == material_id,
                    RawMaterialSupplier.supplier_id == previous,
                )
            )
            if link is not None:
                await self.session.delete(link)
                await self.session.flush()
        if current is not None:
            await self._ensure_link(material_id, current)

    @staticmethod
    def _kind(value: str) -> None:
        if value not in _KINDS:
            raise HTTPException(status_code=400, detail="Kind must be sheet, polish, color, or other")
