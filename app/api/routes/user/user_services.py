from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.api.routes.auth.auth_services import hash_password
from app.api.routes.user.user_model import Role, User
from app.api.routes.user.user_schemas import (
    RoleCreate,
    RoleRead,
    RoleUpdate,
    UserCreate,
    UserRead,
    UserUpdate,
)
from app.api.schemas.pagination import PaginatedResponse, PaginationParams
from app.db.repository import (
    commit_or_conflict,
    create_model,
    delete_model,
    get_or_404,
    list_models,
    to_page,
    update_model,
)


class UserService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_roles(self, pagination: PaginationParams) -> PaginatedResponse[RoleRead]:
        rows, total = await list_models(self.session, Role, pagination)
        return to_page([RoleRead.model_validate(row) for row in rows], total, pagination)

    async def get_role(self, role_id: UUID) -> RoleRead:
        return RoleRead.model_validate(await get_or_404(self.session, Role, role_id))

    async def create_role(self, data: RoleCreate) -> RoleRead:
        row = await create_model(self.session, Role, data)
        return RoleRead.model_validate(row)

    async def update_role(self, role_id: UUID, data: RoleUpdate) -> RoleRead:
        row = await update_model(self.session, Role, role_id, data)
        return RoleRead.model_validate(row)

    async def delete_role(self, role_id: UUID) -> None:
        await delete_model(self.session, Role, role_id)

    async def list_users(self, pagination: PaginationParams) -> PaginatedResponse[UserRead]:
        rows, total = await list_models(self.session, User, pagination)
        return to_page([UserRead.model_validate(row) for row in rows], total, pagination)

    async def get_user(self, user_id: UUID) -> UserRead:
        return UserRead.model_validate(await get_or_404(self.session, User, user_id))

    async def create_user(self, data: UserCreate) -> UserRead:
        payload = data.model_dump()
        payload["email"] = data.email.strip().lower()
        payload["password"] = hash_password(data.password)
        row = User.model_validate(payload)
        self.session.add(row)
        await commit_or_conflict(self.session)
        await self.session.refresh(row)
        return UserRead.model_validate(row)

    async def update_user(self, user_id: UUID, data: UserUpdate) -> UserRead:
        row = await get_or_404(self.session, User, user_id)
        changes = data.model_dump(exclude_unset=True)
        if "email" in changes and changes["email"] is not None:
            changes["email"] = changes["email"].strip().lower()
        if "password" in changes and changes["password"] is not None:
            changes["password"] = hash_password(changes["password"])
        for key, value in changes.items():
            setattr(row, key, value)
        self.session.add(row)
        await commit_or_conflict(self.session)
        await self.session.refresh(row)
        return UserRead.model_validate(row)

    async def delete_user(self, user_id: UUID) -> None:
        await delete_model(self.session, User, user_id)
