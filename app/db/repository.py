from typing import TypeVar
from uuid import UUID

from fastapi import HTTPException, status
from pydantic import BaseModel
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import SQLModel, func, select

from app.api.schemas.pagination import PaginatedResponse, PaginationParams

ModelT = TypeVar("ModelT", bound=SQLModel)


async def commit_or_conflict(session: AsyncSession) -> None:
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Record conflicts with existing data or a missing relation",
        ) from exc


async def get_or_404(session: AsyncSession, model: type[ModelT], entity_id: UUID) -> ModelT:
    row = await session.get(model, entity_id)
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"{model.__name__} not found",
        )
    return row


def apply_changes(row: SQLModel, data: BaseModel) -> None:
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(row, key, value)


async def list_models(
    session: AsyncSession,
    model: type[ModelT],
    pagination: PaginationParams,
) -> tuple[list[ModelT], int]:
    total = await session.scalar(select(func.count()).select_from(model))
    result = await session.scalars(
        select(model)
        .order_by(model.created_at.desc())  # type: ignore[attr-defined]
        .offset(pagination.offset)
        .limit(pagination.page_size)
    )
    return list(result), int(total or 0)


async def create_model(session: AsyncSession, model: type[ModelT], data: BaseModel) -> ModelT:
    row = model.model_validate(data.model_dump())
    session.add(row)
    await commit_or_conflict(session)
    await session.refresh(row)
    return row


async def update_model(
    session: AsyncSession,
    model: type[ModelT],
    entity_id: UUID,
    data: BaseModel,
) -> ModelT:
    row = await get_or_404(session, model, entity_id)
    apply_changes(row, data)
    session.add(row)
    await commit_or_conflict(session)
    await session.refresh(row)
    return row


async def delete_model(session: AsyncSession, model: type[ModelT], entity_id: UUID) -> None:
    row = await get_or_404(session, model, entity_id)
    await session.delete(row)
    await commit_or_conflict(session)


def to_page(items: list, total: int, pagination: PaginationParams) -> PaginatedResponse:
    return PaginatedResponse.from_page(items, total=total, pagination=pagination)
