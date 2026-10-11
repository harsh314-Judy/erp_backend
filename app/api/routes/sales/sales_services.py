from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.api.routes.sales.sales_model import Sale
from app.api.routes.sales.sales_schemas import SaleCreate, SaleRead, SaleUpdate
from app.api.schemas.pagination import PaginatedResponse, PaginationParams
from app.db.repository import (
    create_model,
    delete_model,
    get_or_404,
    list_models,
    to_page,
    update_model,
)


class SalesService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_sales(self, pagination: PaginationParams) -> PaginatedResponse[SaleRead]:
        rows, total = await list_models(self.session, Sale, pagination)
        return to_page([SaleRead.model_validate(row) for row in rows], total, pagination)

    async def get_sale(self, sale_id: UUID) -> SaleRead:
        return SaleRead.model_validate(await get_or_404(self.session, Sale, sale_id))

    async def create_sale(self, data: SaleCreate) -> SaleRead:
        row = await create_model(self.session, Sale, data)
        return SaleRead.model_validate(row)

    async def update_sale(self, sale_id: UUID, data: SaleUpdate) -> SaleRead:
        row = await update_model(self.session, Sale, sale_id, data)
        return SaleRead.model_validate(row)

    async def delete_sale(self, sale_id: UUID) -> None:
        await delete_model(self.session, Sale, sale_id)
