from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.api.routes.raw_material.raw_material_model import RawMaterial
from app.api.routes.raw_material.raw_material_schemas import (
    RawMaterialCreate,
    RawMaterialRead,
    RawMaterialUpdate,
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


class RawMaterialService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_materials(
        self, pagination: PaginationParams
    ) -> PaginatedResponse[RawMaterialRead]:
        rows, total = await list_models(self.session, RawMaterial, pagination)
        return to_page(
            [RawMaterialRead.model_validate(row) for row in rows], total, pagination
        )

    async def get_material(self, material_id: UUID) -> RawMaterialRead:
        return RawMaterialRead.model_validate(
            await get_or_404(self.session, RawMaterial, material_id)
        )

    async def create_material(self, data: RawMaterialCreate) -> RawMaterialRead:
        row = await create_model(self.session, RawMaterial, data)
        return RawMaterialRead.model_validate(row)

    async def update_material(
        self, material_id: UUID, data: RawMaterialUpdate
    ) -> RawMaterialRead:
        row = await update_model(self.session, RawMaterial, material_id, data)
        return RawMaterialRead.model_validate(row)

    async def delete_material(self, material_id: UUID) -> None:
        await delete_model(self.session, RawMaterial, material_id)
