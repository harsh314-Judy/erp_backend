from uuid import UUID

from fastapi import APIRouter, status

from app.api.dependencies import RawMaterialServiceDep
from app.api.routes.raw_material.raw_material_schemas import (
    RawMaterialCreate,
    RawMaterialRead,
    RawMaterialUpdate,
)
from app.api.schemas.pagination import PaginatedResponse, PaginationDep

router = APIRouter(prefix="/raw-materials", tags=["raw materials"])


@router.get("/", response_model=PaginatedResponse[RawMaterialRead])
async def list_materials(
    service: RawMaterialServiceDep, pagination: PaginationDep
) -> PaginatedResponse[RawMaterialRead]:
    return await service.list_materials(pagination)


@router.post("/", response_model=RawMaterialRead, status_code=status.HTTP_201_CREATED)
async def create_material(
    data: RawMaterialCreate, service: RawMaterialServiceDep
) -> RawMaterialRead:
    return await service.create_material(data)


@router.get("/{material_id}", response_model=RawMaterialRead)
async def get_material(material_id: UUID, service: RawMaterialServiceDep) -> RawMaterialRead:
    return await service.get_material(material_id)


@router.patch("/{material_id}", response_model=RawMaterialRead)
async def update_material(
    material_id: UUID, data: RawMaterialUpdate, service: RawMaterialServiceDep
) -> RawMaterialRead:
    return await service.update_material(material_id, data)


@router.delete("/{material_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_material(material_id: UUID, service: RawMaterialServiceDep) -> None:
    await service.delete_material(material_id)
