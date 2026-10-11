from uuid import UUID

from fastapi import APIRouter, Response, status

from app.api.dependencies import AdminUserDep, CurrentUserDep, UserServiceDep
from app.api.routes.user.user_schemas import (
    PasswordChangeRequest,
    RoleCreate,
    RoleRead,
    RoleUpdate,
    UserCreate,
    UserRead,
    UserUpdate,
)
from app.api.schemas.common import MessageResponse
from app.api.schemas.pagination import PaginatedResponse, PaginationDep
from app.api.security.cookies import clear_auth_cookies

router = APIRouter(tags=["users"])


@router.get("/roles", response_model=PaginatedResponse[RoleRead])
async def list_roles(
    service: UserServiceDep, pagination: PaginationDep, _: AdminUserDep
) -> PaginatedResponse[RoleRead]:
    return await service.list_roles(pagination)


@router.post("/roles", response_model=RoleRead, status_code=status.HTTP_201_CREATED)
async def create_role(
    data: RoleCreate, service: UserServiceDep, _: AdminUserDep
) -> RoleRead:
    return await service.create_role(data)


@router.get("/roles/{role_id}", response_model=RoleRead)
async def get_role(role_id: UUID, service: UserServiceDep, _: AdminUserDep) -> RoleRead:
    return await service.get_role(role_id)


@router.patch("/roles/{role_id}", response_model=RoleRead)
async def update_role(
    role_id: UUID, data: RoleUpdate, service: UserServiceDep, _: AdminUserDep
) -> RoleRead:
    return await service.update_role(role_id, data)


@router.delete("/roles/{role_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_role(role_id: UUID, service: UserServiceDep, _: AdminUserDep) -> None:
    await service.delete_role(role_id)


@router.get("/users/me", response_model=UserRead)
async def get_me(user: CurrentUserDep, service: UserServiceDep) -> UserRead:
    return await service.get_user(user.id)


@router.post("/users/me/password", response_model=MessageResponse)
async def change_password(
    data: PasswordChangeRequest,
    user: CurrentUserDep,
    service: UserServiceDep,
    response: Response,
) -> MessageResponse:
    result = await service.change_password(user, data)
    clear_auth_cookies(response)
    return result


@router.get("/users", response_model=PaginatedResponse[UserRead])
async def list_users(
    service: UserServiceDep,
    pagination: PaginationDep,
    _: AdminUserDep,
) -> PaginatedResponse[UserRead]:
    return await service.list_users(pagination)


@router.post("/users", response_model=UserRead, status_code=status.HTTP_201_CREATED)
async def create_user(
    data: UserCreate, service: UserServiceDep, actor: AdminUserDep
) -> UserRead:
    return await service.create_user(data, actor)


@router.get("/users/{user_id}", response_model=UserRead)
async def get_user(
    user_id: UUID, service: UserServiceDep, _: AdminUserDep
) -> UserRead:
    return await service.get_user(user_id)


@router.patch("/users/{user_id}", response_model=UserRead)
async def update_user(
    user_id: UUID,
    data: UserUpdate,
    service: UserServiceDep,
    actor: AdminUserDep,
) -> UserRead:
    return await service.update_user(user_id, data, actor)


@router.delete("/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(user_id: UUID, service: UserServiceDep, _: AdminUserDep) -> None:
    await service.delete_user(user_id)
