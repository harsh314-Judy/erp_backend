import logging

from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.api.routes.auth.auth_services import hash_password
from app.api.routes.user.user_model import Role, User
from app.config import auth_settings

logger = logging.getLogger(__name__)

_BOOTSTRAP_ROLES = ("super_admin", "admin", "accountant", "staff")


async def bootstrap_super_admin(session: AsyncSession) -> None:
    for role_name in _BOOTSTRAP_ROLES:
        existing = await session.scalar(select(Role).where(Role.role_name == role_name))
        if existing is None:
            session.add(Role(role_name=role_name))
    await session.commit()

    email = auth_settings.SUPER_ADMIN_EMAIL
    password = auth_settings.SUPER_ADMIN_PASSWORD
    if not email or not password:
        logger.info("super admin bootstrap skipped; email or password is empty")
        return
    existing_user = await session.scalar(select(User).where(User.email == email))
    if existing_user is not None:
        return
    role = await session.scalar(select(Role).where(Role.role_name == "super_admin"))
    if role is None:
        return
    session.add(
        User(
            first_name=auth_settings.SUPER_ADMIN_FIRST_NAME.strip() or "Super",
            last_name=auth_settings.SUPER_ADMIN_LAST_NAME.strip() or None,
            email=email,
            password=hash_password(password),
            role_id=role.id,
        )
    )
    await session.commit()
    logger.info("created super admin %s", email)
