from uuid import UUID

from fastapi import APIRouter, status

from app.api.dependencies import UserServiceDep
from app.api.routes.user.user_schemas import (
    RoleCreate,
    RoleRead,
    RoleUpdate,
    UserCreate,
    UserRead,
    UserUpdate,
)
from app.api.schemas.pagination import PaginatedResponse, PaginationDep

router = APIRouter(tags=["users"])


@router.get("/roles", response_model=PaginatedResponse[RoleRead])
async def list_roles(
    service: UserServiceDep, pagination: PaginationDep
) -> PaginatedResponse[RoleRead]:
    return await service.list_roles(pagination)


@router.post("/roles", response_model=RoleRead, status_code=status.HTTP_201_CREATED)
async def create_role(data: RoleCreate, service: UserServiceDep) -> RoleRead:
    return await service.create_role(data)


@router.get("/roles/{role_id}", response_model=RoleRead)
async def get_role(role_id: UUID, service: UserServiceDep) -> RoleRead:
    return await service.get_role(role_id)


@router.patch("/roles/{role_id}", response_model=RoleRead)
async def update_role(
    role_id: UUID, data: RoleUpdate, service: UserServiceDep
) -> RoleRead:
    return await service.update_role(role_id, data)


@router.delete("/roles/{role_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_role(role_id: UUID, service: UserServiceDep) -> None:
    await service.delete_role(role_id)


@router.get("/users", response_model=PaginatedResponse[UserRead])
async def list_users(
    service: UserServiceDep, pagination: PaginationDep
) -> PaginatedResponse[UserRead]:
    return await service.list_users(pagination)


@router.post("/users", response_model=UserRead, status_code=status.HTTP_201_CREATED)
async def create_user(data: UserCreate, service: UserServiceDep) -> UserRead:
    return await service.create_user(data)


@router.get("/users/{user_id}", response_model=UserRead)
async def get_user(user_id: UUID, service: UserServiceDep) -> UserRead:
    return await service.get_user(user_id)


@router.patch("/users/{user_id}", response_model=UserRead)
async def update_user(
    user_id: UUID, data: UserUpdate, service: UserServiceDep
) -> UserRead:
    return await service.update_user(user_id, data)


@router.delete("/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(user_id: UUID, service: UserServiceDep) -> None:
    await service.delete_user(user_id)
