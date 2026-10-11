from uuid import UUID

from fastapi import APIRouter, status

from app.api.dependencies import CustomerServiceDep
from app.api.routes.customer.customer_schemas import (
    CustomerCreate,
    CustomerRead,
    CustomerUpdate,
)
from app.api.schemas.pagination import PaginatedResponse, PaginationDep

router = APIRouter(prefix="/customers", tags=["customers"])


@router.get("/", response_model=PaginatedResponse[CustomerRead])
async def list_customers(
    service: CustomerServiceDep, pagination: PaginationDep
) -> PaginatedResponse[CustomerRead]:
    return await service.list_customers(pagination)


@router.post("/", response_model=CustomerRead, status_code=status.HTTP_201_CREATED)
async def create_customer(data: CustomerCreate, service: CustomerServiceDep) -> CustomerRead:
    return await service.create_customer(data)


@router.get("/{customer_id}", response_model=CustomerRead)
async def get_customer(customer_id: UUID, service: CustomerServiceDep) -> CustomerRead:
    return await service.get_customer(customer_id)


@router.patch("/{customer_id}", response_model=CustomerRead)
async def update_customer(
    customer_id: UUID, data: CustomerUpdate, service: CustomerServiceDep
) -> CustomerRead:
    return await service.update_customer(customer_id, data)


@router.delete("/{customer_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_customer(customer_id: UUID, service: CustomerServiceDep) -> None:
    await service.delete_customer(customer_id)
