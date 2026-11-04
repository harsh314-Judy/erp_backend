from fastapi import APIRouter, Query

from app.api.db_dependency import PGSessionDep
from app.api.dependencies import CurrentUserDep, TradingServiceDep
from app.api.routes.trading.trading_services import role_name_for
from app.api.security.permissions import VIEW_INVENTORY, forbid, role_has

router = APIRouter(prefix="/trading", tags=["trading"])


@router.get("/items")
async def trading_items(
    service: TradingServiceDep, session: PGSessionDep, user: CurrentUserDep
) -> list[dict]:
    name = await role_name_for(session, user)
    if not role_has(name, VIEW_INVENTORY):
        forbid()
    return await service.items(name)


@router.get("/summary")
async def trading_summary(
    service: TradingServiceDep,
    session: PGSessionDep,
    user: CurrentUserDep,
    period: str = Query(default="month"),
) -> dict:
    name = await role_name_for(session, user)
    if not role_has(name, VIEW_INVENTORY):
        forbid()
    return await service.summary(name, period)
