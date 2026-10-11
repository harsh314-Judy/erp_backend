from uuid import UUID

from fastapi import APIRouter, status

from app.api.dependencies import SalesServiceDep
from app.api.routes.sales.sales_schemas import SaleCreate, SaleRead, SaleUpdate
from app.api.schemas.pagination import PaginatedResponse, PaginationDep

router = APIRouter(prefix="/sales", tags=["sales"])


@router.get("/", response_model=PaginatedResponse[SaleRead])
async def list_sales(
    service: SalesServiceDep, pagination: PaginationDep
) -> PaginatedResponse[SaleRead]:
    return await service.list_sales(pagination)


@router.post("/", response_model=SaleRead, status_code=status.HTTP_201_CREATED)
async def create_sale(data: SaleCreate, service: SalesServiceDep) -> SaleRead:
    return await service.create_sale(data)


@router.get("/{sale_id}", response_model=SaleRead)
async def get_sale(sale_id: UUID, service: SalesServiceDep) -> SaleRead:
    return await service.get_sale(sale_id)


@router.patch("/{sale_id}", response_model=SaleRead)
async def update_sale(
    sale_id: UUID, data: SaleUpdate, service: SalesServiceDep
) -> SaleRead:
    return await service.update_sale(sale_id, data)


@router.delete("/{sale_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_sale(sale_id: UUID, service: SalesServiceDep) -> None:
    await service.delete_sale(sale_id)
