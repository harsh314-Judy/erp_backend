from fastapi import Request

from app.config import auth_settings


def client_ip(request: Request) -> str:
    trusted = auth_settings.TRUSTED_PROXY_COUNT
    if trusted > 0:
        forwarded = request.headers.get("x-forwarded-for", "")
        parts = [part.strip() for part in forwarded.split(",") if part.strip()]
        if parts:
            index = max(0, len(parts) - trusted)
            return parts[index]
    if request.client and request.client.host:
        return request.client.host
    return "unknown"
