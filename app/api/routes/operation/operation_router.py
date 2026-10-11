from uuid import UUID

from fastapi import APIRouter, status

from app.api.dependencies import OperationServiceDep
from app.api.routes.operation.operation_schemas import (
    OperationCreate,
    OperationRead,
    OperationUpdate,
    UserOperationCreate,
    UserOperationRead,
)
from app.api.schemas.pagination import PaginatedResponse, PaginationDep

router = APIRouter(tags=["operations"])


@router.get("/operations", response_model=PaginatedResponse[OperationRead])
async def list_operations(
    service: OperationServiceDep, pagination: PaginationDep
) -> PaginatedResponse[OperationRead]:
    return await service.list_operations(pagination)


@router.post("/operations", response_model=OperationRead, status_code=status.HTTP_201_CREATED)
async def create_operation(
    data: OperationCreate, service: OperationServiceDep
) -> OperationRead:
    return await service.create_operation(data)


@router.patch("/operations/{operation_id}", response_model=OperationRead)
async def update_operation(
    operation_id: UUID, data: OperationUpdate, service: OperationServiceDep
) -> OperationRead:
    return await service.update_operation(operation_id, data)


@router.delete("/operations/{operation_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_operation(operation_id: UUID, service: OperationServiceDep) -> None:
    await service.delete_operation(operation_id)


@router.get("/user-operations", response_model=PaginatedResponse[UserOperationRead])
async def list_assignments(
    service: OperationServiceDep, pagination: PaginationDep
) -> PaginatedResponse[UserOperationRead]:
    return await service.list_assignments(pagination)


@router.post(
    "/user-operations",
    response_model=UserOperationRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_assignment(
    data: UserOperationCreate, service: OperationServiceDep
) -> UserOperationRead:
    return await service.create_assignment(data)


@router.delete("/user-operations/{assignment_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_assignment(assignment_id: UUID, service: OperationServiceDep) -> None:
    await service.delete_assignment(assignment_id)
