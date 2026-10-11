from uuid import UUID

from fastapi import APIRouter, status

from app.api.dependencies import ProductionServiceDep
from app.api.routes.production.production_schemas import (
    ProductionJobCreate,
    ProductionJobRead,
    ProductionJobUpdate,
)
from app.api.schemas.pagination import PaginatedResponse, PaginationDep

router = APIRouter(prefix="/production-jobs", tags=["production"])


@router.get("/", response_model=PaginatedResponse[ProductionJobRead])
async def list_jobs(
    service: ProductionServiceDep, pagination: PaginationDep
) -> PaginatedResponse[ProductionJobRead]:
    return await service.list_jobs(pagination)


@router.post("/", response_model=ProductionJobRead, status_code=status.HTTP_201_CREATED)
async def create_job(
    data: ProductionJobCreate, service: ProductionServiceDep
) -> ProductionJobRead:
    return await service.create_job(data)


@router.get("/{job_id}", response_model=ProductionJobRead)
async def get_job(job_id: UUID, service: ProductionServiceDep) -> ProductionJobRead:
    return await service.get_job(job_id)


@router.patch("/{job_id}", response_model=ProductionJobRead)
async def update_job(
    job_id: UUID, data: ProductionJobUpdate, service: ProductionServiceDep
) -> ProductionJobRead:
    return await service.update_job(job_id, data)


@router.delete("/{job_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_job(job_id: UUID, service: ProductionServiceDep) -> None:
    await service.delete_job(job_id)
