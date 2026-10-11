from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.api.routes.production.production_model import ProductionJob
from app.api.routes.production.production_schemas import (
    ProductionJobCreate,
    ProductionJobRead,
    ProductionJobUpdate,
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


class ProductionService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_jobs(
        self, pagination: PaginationParams
    ) -> PaginatedResponse[ProductionJobRead]:
        rows, total = await list_models(self.session, ProductionJob, pagination)
        return to_page(
            [ProductionJobRead.model_validate(row) for row in rows], total, pagination
        )

    async def get_job(self, job_id: UUID) -> ProductionJobRead:
        return ProductionJobRead.model_validate(
            await get_or_404(self.session, ProductionJob, job_id)
        )

    async def create_job(self, data: ProductionJobCreate) -> ProductionJobRead:
        row = await create_model(self.session, ProductionJob, data)
        return ProductionJobRead.model_validate(row)

    async def update_job(self, job_id: UUID, data: ProductionJobUpdate) -> ProductionJobRead:
        row = await update_model(self.session, ProductionJob, job_id, data)
        return ProductionJobRead.model_validate(row)

    async def delete_job(self, job_id: UUID) -> None:
        await delete_model(self.session, ProductionJob, job_id)
