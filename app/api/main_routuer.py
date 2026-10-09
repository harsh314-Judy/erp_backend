from fastapi import APIRouter

from app.api.routes.auth import auth_routes
from app.api.routes.health import health_routes

main_router = APIRouter(prefix="/api/")

# Public
main_router.include_router(health_routes.router)
