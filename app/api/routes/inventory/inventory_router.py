from fastapi import APIRouter, status

from app.api.db_dependency import PGSessionDep
from app.api.dependencies import CurrentUserDep, InventoryServiceDep
from app.api.routes.inventory.inventory_schemas import AdjustmentCreate, StockRequestCreate
from app.api.routes.user.user_model import Role
from app.api.security.permissions import EDIT_INVENTORY, VIEW_INVENTORY, forbid, role_has

router = APIRouter(prefix="/inventory", tags=["inventory"])


async def _allow(session: PGSessionDep, user: CurrentUserDep, capability: str) -> None:
    role = await session.get(Role, user.role_id)
    if not role_has(role.role_name if role else None, capability):
        forbid()


@router.post("/adjustments", status_code=status.HTTP_204_NO_CONTENT)
async def adjust_stock(
    data: AdjustmentCreate,
    service: InventoryServiceDep,
    session: PGSessionDep,
    user: CurrentUserDep,
) -> None:
    await _allow(session, user, EDIT_INVENTORY)
    await service.adjust(
        actor=user,
        quantity_delta=data.quantity_delta,
        reason=data.reason,
        product_id=data.product_id,
        raw_material_id=data.raw_material_id,
    )


@router.post("/requests", status_code=status.HTTP_201_CREATED)
async def request_stock(
    data: StockRequestCreate,
    service: InventoryServiceDep,
    session: PGSessionDep,
    user: CurrentUserDep,
) -> dict:
    await _allow(session, user, VIEW_INVENTORY)
    row = await service.request_stock(
        actor=user,
        quantity=data.quantity,
        note=data.note,
        product_id=data.product_id,
        raw_material_id=data.raw_material_id,
    )
    return {"id": row.id, "status": row.status}
