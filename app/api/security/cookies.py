import hashlib
import hmac
import secrets

from fastapi import Response

from app.config import auth_settings

ACCESS_COOKIE = "access_token"
REFRESH_COOKIE = "refresh_token"
CSRF_COOKIE = "csrf_token"
CSRF_HEADER = "x-csrf-token"


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def hash_ip(ip: str) -> str:
    return hmac.new(
        auth_settings.JWT_SECRET.encode(),
        ip.encode(),
        hashlib.sha256,
    ).hexdigest()


def new_secret() -> str:
    return secrets.token_urlsafe(32)


def set_auth_cookies(
    response: Response,
    *,
    access_token: str,
    refresh_token: str,
    csrf_token: str,
) -> None:
    secure = auth_settings.COOKIE_SECURE
    samesite = auth_settings.COOKIE_SAMESITE
    access_age = auth_settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
    refresh_age = auth_settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60
    response.set_cookie(
        ACCESS_COOKIE,
        access_token,
        httponly=True,
        secure=secure,
        samesite=samesite,
        path="/",
        max_age=access_age,
    )
    response.set_cookie(
        REFRESH_COOKIE,
        refresh_token,
        httponly=True,
        secure=secure,
        samesite=samesite,
        path="/api/auth",
        max_age=refresh_age,
    )
    response.set_cookie(
        CSRF_COOKIE,
        csrf_token,
        httponly=False,
        secure=secure,
        samesite=samesite,
        path="/",
        max_age=access_age,
    )


def clear_auth_cookies(response: Response) -> None:
    secure = auth_settings.COOKIE_SECURE
    samesite = auth_settings.COOKIE_SAMESITE
    response.delete_cookie(ACCESS_COOKIE, path="/", secure=secure, samesite=samesite)
    response.delete_cookie(
        REFRESH_COOKIE,
        path="/api/auth",
        secure=secure,
        samesite=samesite,
    )
    response.delete_cookie(CSRF_COOKIE, path="/", secure=secure, samesite=samesite)
