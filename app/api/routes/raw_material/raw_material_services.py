from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import func, select

from app.api.routes.inventory.inventory_services import InventoryService
from app.api.routes.raw_material.raw_material_model import RawMaterial
from app.api.routes.raw_material.raw_material_schemas import (
    RawMaterialCreate,
    RawMaterialOption,
    RawMaterialRead,
    RawMaterialUpdate,
)
from app.api.schemas.pagination import PaginatedResponse, PaginationParams
from app.db.repository import create_model, delete_model, get_or_404, to_page, update_model

_KINDS = {"sheet", "polish", "color", "other"}


class RawMaterialService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_materials(
        self, pagination: PaginationParams, *, query: str | None, show_prices: bool
    ) -> PaginatedResponse[RawMaterialRead]:
        statement = select(RawMaterial)
        count = select(func.count()).select_from(RawMaterial)
        if query:
            like = f"%{query.strip()}%"
            statement = statement.where(RawMaterial.name.ilike(like))
            count = count.where(RawMaterial.name.ilike(like))
        total = int(await self.session.scalar(count) or 0)
        result = await self.session.scalars(
            statement.order_by(RawMaterial.name).offset(pagination.offset).limit(pagination.page_size)
        )
        return to_page([await self._present(row, show_prices) for row in result], total, pagination)

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
        row = await create_model(self.session, RawMaterial, data)
        return await self._present(row, show_prices)

    async def update_material(
        self, material_id: UUID, data: RawMaterialUpdate, *, show_prices: bool
    ) -> RawMaterialRead:
        if data.kind is not None:
            self._kind(data.kind)
        row = await update_model(self.session, RawMaterial, material_id, data)
        return await self._present(row, show_prices)

    async def delete_material(self, material_id: UUID) -> None:
        await delete_model(self.session, RawMaterial, material_id)

    async def _present(self, row: RawMaterial, show_prices: bool) -> RawMaterialRead:
        snapshot = await InventoryService(self.session).material_snapshot(row)
        data = RawMaterialRead.model_validate(row).model_copy(
            update={
                "on_hand": snapshot["on_hand"],
                "held": snapshot["held"],
                "available": snapshot["available"],
                "stock_status": snapshot["status"],
            }
        )
        if not show_prices:
            data.price = None
            data.purchase_price = None
        return data

    @staticmethod
    def _kind(value: str) -> None:
        if value not in _KINDS:
            raise HTTPException(status_code=400, detail="Kind must be sheet, polish, color, or other")
