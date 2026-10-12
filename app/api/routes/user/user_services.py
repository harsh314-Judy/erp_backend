from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import func, select

from app.api.routes.auth.auth_services import (
    hash_password,
    revoke_refresh_tokens,
    verify_password,
)
from app.api.routes.auth.rate_limit import (
    PROFILE_PASSWORD,
    ensure_allowed,
    record_attempt,
)
from app.api.routes.user.user_model import MANAGED_BY_ADMIN, SYSTEM_ROLES, Role, User
from app.api.routes.user.user_schemas import (
    PasswordChangeRequest,
    ProfileUpdate,
    RoleCreate,
    RoleRead,
    RoleUpdate,
    UserCreate,
    UserRead,
    UserUpdate,
)
from app.api.schemas.common import MessageResponse
from app.api.schemas.pagination import PaginatedResponse, PaginationParams
from app.config import auth_settings
from app.db.repository import (
    commit_or_conflict,
    create_model,
    delete_model,
    get_or_404,
    list_models,
    to_page,
    update_model,
)


_IDENTITY_FIELDS = ("first_name", "last_name", "email")


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
        role = await get_or_404(self.session, Role, role_id)
        if role.role_name in SYSTEM_ROLES and data.role_name not in {None, role.role_name}:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="This role cannot be renamed",
            )
        row = await update_model(self.session, Role, role_id, data)
        return RoleRead.model_validate(row)

    async def delete_role(self, role_id: UUID) -> None:
        role = await get_or_404(self.session, Role, role_id)
        if role.role_name in SYSTEM_ROLES:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="This role cannot be deleted",
            )
        await delete_model(self.session, Role, role_id)

    async def list_users(self, pagination: PaginationParams) -> PaginatedResponse[UserRead]:
        rows, total = await list_models(self.session, User, pagination)
        items = [await self._read(row) for row in rows]
        return to_page(items, total, pagination)

    async def get_user(self, user_id: UUID) -> UserRead:
        return await self._read(await get_or_404(self.session, User, user_id))

    async def create_user(self, data: UserCreate, actor: User) -> UserRead:
        await self._guard_super_admin_assignment(actor, data.role_id)
        payload = data.model_dump()
        payload["email"] = data.email.strip().lower()
        payload["password"] = hash_password(data.password)
        row = User.model_validate(payload)
        self.session.add(row)
        await commit_or_conflict(self.session)
        await self.session.refresh(row)
        return await self._read(row)

    async def update_profile(self, actor: User, data: ProfileUpdate) -> UserRead:
        return await self.update_user(
            actor.id,
            UserUpdate(
                first_name=data.first_name,
                last_name=data.last_name,
                email=data.email,
            ),
            actor,
        )

    async def update_user(self, user_id: UUID, data: UserUpdate, actor: User) -> UserRead:
        row = await get_or_404(self.session, User, user_id)
        changes = data.model_dump(exclude_unset=True)
        if "role_id" in changes and changes["role_id"] is not None:
            await self._guard_super_admin_assignment(actor, changes["role_id"])
            await self._guard_last_super_admin(row, changes["role_id"])
        if "first_name" in changes and changes["first_name"] is not None:
            changes["first_name"] = changes["first_name"].strip()
        if "last_name" in changes:
            last_name = changes["last_name"]
            changes["last_name"] = (
                last_name.strip() if isinstance(last_name, str) and last_name.strip() else None
            )
        if "email" in changes and changes["email"] is not None:
            changes["email"] = changes["email"].strip().lower()
        if "password" in changes and changes["password"] is not None:
            changes["password"] = hash_password(changes["password"])
        await self._apply_identity_rules(row, actor, changes)
        for key, value in changes.items():
            setattr(row, key, value)
        self.session.add(row)
        await commit_or_conflict(self.session)
        await self.session.refresh(row)
        return await self._read(row)

    async def delete_user(self, user_id: UUID) -> None:
        row = await get_or_404(self.session, User, user_id)
        await self._guard_last_super_admin(row, None)
        await revoke_refresh_tokens(self.session, row.id)
        await self.session.delete(row)
        await commit_or_conflict(self.session)

    async def change_password(
        self, user: User, data: PasswordChangeRequest
    ) -> MessageResponse:
        if not verify_password(data.old_password, user.password):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Old password is incorrect",
            )
        await ensure_allowed(
            self.session,
            action=PROFILE_PASSWORD,
            user_id=user.id,
            daily=True,
            message="Password changes are locked until tomorrow",
        )
        user.password = hash_password(data.new_password)
        await revoke_refresh_tokens(self.session, user.id)
        await record_attempt(
            self.session,
            action=PROFILE_PASSWORD,
            user_id=user.id,
            max_count=auth_settings.PROFILE_PASSWORD_MAX_PER_DAY,
            lock_hours=24,
            daily=True,
        )
        self.session.add(user)
        await commit_or_conflict(self.session)
        return MessageResponse(message="Password updated")

    async def _read(self, user: User) -> UserRead:
        role = await self.session.get(Role, user.role_id)
        return UserRead.model_validate(user).model_copy(
            update={"role_name": role.role_name if role else None}
        )

    async def _apply_identity_rules(self, row: User, actor: User, changes: dict) -> None:
        identity_changes = {
            field: changes[field]
            for field in _IDENTITY_FIELDS
            if field in changes and changes[field] != getattr(row, field)
        }
        wants_flag = "identity_overridden" in changes
        if not identity_changes and not wants_flag:
            return

        actor_role = await get_or_404(self.session, Role, actor.role_id)
        target_role = await get_or_404(self.session, Role, row.role_id)
        is_super_admin = actor_role.role_name == "super_admin"
        if wants_flag and not is_super_admin:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only a super admin can override a name or email",
            )
        if identity_changes and not self._may_edit_identity(
            actor_role.role_name,
            target_role.role_name,
            is_self=actor.id == row.id,
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You cannot edit this account's name or email",
            )
        if row.identity_overridden and identity_changes and not is_super_admin:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only a super admin can override this name and email",
            )
        if is_super_admin and identity_changes and not wants_flag:
            changes["identity_overridden"] = True

    @staticmethod
    def _may_edit_identity(actor_role: str, target_role: str, *, is_self: bool) -> bool:
        if actor_role == "super_admin" or is_self:
            return True
        return actor_role == "admin" and target_role in MANAGED_BY_ADMIN

    async def _guard_super_admin_assignment(self, actor: User, role_id: UUID) -> None:
        role = await get_or_404(self.session, Role, role_id)
        if role.role_name != "super_admin":
            return
        actor_role = await get_or_404(self.session, Role, actor.role_id)
        if actor_role.role_name != "super_admin":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only a super admin can assign the super admin role",
            )

    async def _guard_last_super_admin(self, user: User, next_role_id: UUID | None) -> None:
        role = await self.session.get(Role, user.role_id)
        if role is None or role.role_name != "super_admin":
            return
        if next_role_id == user.role_id:
            return
        total = await self.session.scalar(
            select(func.count()).select_from(User).where(User.role_id == user.role_id)
        )
        if int(total or 0) <= 1:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="The last super admin cannot be removed",
            )
