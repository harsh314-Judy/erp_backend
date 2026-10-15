from uuid import UUID

from fastapi import APIRouter

from app.api.db_dependency import PGSessionDep
from app.api.dependencies import CurrentUserDep, ReportServiceDep
from app.api.routes.inventory.inventory_services import InventoryService, movement_visible
from app.api.routes.report.report_schemas import DashboardRead, ProductionReport, SalesReport
from app.api.routes.user.user_model import Role
from app.api.security.permissions import VIEW_FINANCIALS, VIEW_REPORTS, can_see_prices, forbid, role_has

router = APIRouter(tags=["reports"])


async def _role(session: PGSessionDep, user: CurrentUserDep) -> str:
    role = await session.get(Role, user.role_id)
    name = role.role_name if role else ""
    if not role_has(name, VIEW_REPORTS):
        forbid()
    return name


@router.get("/dashboard", response_model=DashboardRead)
async def dashboard(
    service: ReportServiceDep, user: CurrentUserDep
) -> DashboardRead:
    return await service.dashboard(user)


@router.get("/reports/sales", response_model=SalesReport, response_model_exclude_none=True)
async def sales_report(
    service: ReportServiceDep, session: PGSessionDep, user: CurrentUserDep
) -> SalesReport:
    await _role(session, user)
    return await service.sales_report(user)


@router.get("/reports/production", response_model=ProductionReport)
async def production_report(
    service: ReportServiceDep, session: PGSessionDep, user: CurrentUserDep
) -> ProductionReport:
    name = await _role(session, user)
    if name == "staff":
        forbid()
    return await service.production_report()


@router.get("/reports/inventory")
async def inventory_report(
    service: ReportServiceDep,
    session: PGSessionDep,
    user: CurrentUserDep,
    product_id: UUID | None = None,
    raw_material_id: UUID | None = None,
    user_id: UUID | None = None,
) -> dict:
    name = await _role(session, user)
    movements = await InventoryService(session).list_movements(
        product_id=product_id, raw_material_id=raw_material_id, user_id=user_id
    )
    return {
        "stock": await service.inventory_rows(),
        "movements": [
            movement_visible(row, prices=can_see_prices(name) or role_has(name, VIEW_FINANCIALS))
            for row in movements
        ],
    }
