from typing import Annotated

from fastapi import Depends

from app.api.db_dependency import GarageClientDep, PGSessionDep
from app.api.routes.health.health_service import HealthService


def get_health_service(
    pg_session: PGSessionDep,
    garage_client: GarageClientDep,
) -> HealthService:
    return HealthService(pg_session, garage_client)


type HealthServiceDep = Annotated[HealthService, Depends(get_health_service)]
