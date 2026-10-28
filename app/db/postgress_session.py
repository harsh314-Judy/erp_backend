# app/db/postgress_session.py

from typing import AsyncGenerator

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.config import db_settings

_engine: AsyncEngine | None = None


def async_engine() -> AsyncEngine:
    if _engine is None:
        raise RuntimeError("Database engine is not ready")
    return _engine


class PostgresSession:
    """Manages the PostgreSQL database connection and sessions."""

    def __init__(self) -> None:
        global _engine
        self._engine: AsyncEngine = create_async_engine(
            db_settings.POSTGRES_URL,
            echo=db_settings.POSTGRES_ECHO,
            pool_size=10,
            max_overflow=5,
            pool_timeout=30,
            pool_recycle=280,
            connect_args={
                "ssl": db_settings.POSTGRES_SSL,
                "server_settings": {"timezone": "UTC"},
            },
        )
        _engine = self._engine
        self._sessionmaker: async_sessionmaker[AsyncSession] = async_sessionmaker(
            bind=self._engine,
            expire_on_commit=False,
            class_=AsyncSession,
        )

    async def verify_connection(self) -> None:
        """Verify the connection pool works at startup."""
        async with self._sessionmaker() as session:
            await session.execute(text("SELECT 1"))

    async def get_session(self) -> AsyncGenerator[AsyncSession, None]:
        async with self._sessionmaker() as session:
            yield session

    async def dispose(self) -> None:
        await self._engine.dispose()