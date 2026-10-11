from uuid import UUID

from jose import JWTError, jwt
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.api.security.cookies import ACCESS_COOKIE
from app.config import auth_settings

_PUBLIC_PREFIXES = ("/docs", "/redoc", "/openapi.json")
_PUBLIC_PATHS = {
    "/health",
    "/api/health/live",
    "/api/health/ready",
    "/api/auth/login",
    "/api/auth/refresh",
    "/api/auth/logout",
    "/api/auth/signup",
    "/api/auth/forgot-password",
    "/api/auth/resend-reset",
    "/api/auth/reset-password",
}


def _is_public(path: str) -> bool:
    normalized = path.rstrip("/") or "/"
    if normalized in _PUBLIC_PATHS:
        return True
    return any(path == prefix or path.startswith(f"{prefix}/") for prefix in _PUBLIC_PREFIXES)


class AccessTokenMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        if request.method == "OPTIONS" or _is_public(request.url.path):
            return await call_next(request)

        token = request.cookies.get(ACCESS_COOKIE)
        if not token:
            return JSONResponse(
                status_code=401,
                content={"detail": "Access token is missing or expired"},
            )
        try:
            payload = jwt.decode(
                token,
                auth_settings.JWT_SECRET,
                algorithms=[auth_settings.JWT_ALGORITHM],
            )
            user_id = UUID(str(payload["sub"]))
        except (JWTError, ValueError, KeyError):
            return JSONResponse(
                status_code=401,
                content={"detail": "Access token is missing or expired"},
            )
        request.state.user_id = user_id
        return await call_next(request)
