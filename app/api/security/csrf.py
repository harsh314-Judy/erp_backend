import secrets

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.api.security.cookies import CSRF_COOKIE, CSRF_HEADER

_SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}
_PUBLIC_AUTH_PATHS = {
    "/api/auth/login",
    "/api/auth/refresh",
    "/api/auth/logout",
    "/api/auth/signup",
    "/api/auth/forgot-password",
    "/api/auth/resend-reset",
    "/api/auth/reset-password",
}


def _skips_csrf(request: Request) -> bool:
    if request.method in _SAFE_METHODS:
        return True
    path = request.url.path.rstrip("/") or "/"
    if path in _PUBLIC_AUTH_PATHS:
        return True
    if path == "/api/health" or path.startswith("/api/health/"):
        return True
    if path == "/health":
        return True
    return False


class CsrfMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        if _skips_csrf(request):
            return await call_next(request)

        cookie = request.cookies.get(CSRF_COOKIE)
        header = request.headers.get(CSRF_HEADER)
        if not cookie or not header or not secrets.compare_digest(cookie, header):
            return JSONResponse(
                status_code=403,
                content={"detail": "CSRF token is missing or invalid"},
            )
        return await call_next(request)
