from fastapi import APIRouter, HTTPException, Request, Response, status

from app.api.dependencies import AdminUserDep, AuthServiceDep
from app.api.routes.auth.auth_schemas import (
    ForgotPasswordRequest,
    InviteCreate,
    LoginRequest,
    ResetPasswordRequest,
    SignupRequest,
)
from app.api.routes.user.user_schemas import UserRead
from app.api.schemas.common import MessageResponse
from app.api.security.client_ip import client_ip
from app.api.security.cookies import REFRESH_COOKIE, clear_auth_cookies, set_auth_cookies

router = APIRouter(prefix="/auth", tags=["auth"])


def _apply_session(response: Response, issued) -> None:
    set_auth_cookies(
        response,
        access_token=issued.access_token,
        refresh_token=issued.refresh_token,
        csrf_token=issued.csrf_token,
    )


@router.post("/invites", response_model=MessageResponse, status_code=status.HTTP_201_CREATED)
async def create_invite(
    data: InviteCreate,
    service: AuthServiceDep,
    actor: AdminUserDep,
) -> MessageResponse:
    return await service.create_invite(data, actor)


@router.post("/signup", response_model=UserRead, status_code=status.HTTP_201_CREATED)
async def signup(
    data: SignupRequest,
    request: Request,
    response: Response,
    service: AuthServiceDep,
) -> UserRead:
    issued = await service.signup(data, client_ip(request))
    _apply_session(response, issued)
    return issued.user


@router.post("/login", response_model=UserRead)
async def login(
    data: LoginRequest,
    request: Request,
    response: Response,
    service: AuthServiceDep,
) -> UserRead:
    issued = await service.login(data, client_ip(request))
    _apply_session(response, issued)
    return issued.user


@router.post("/refresh", response_model=MessageResponse)
async def refresh(
    request: Request, response: Response, service: AuthServiceDep
) -> MessageResponse:
    raw = request.cookies.get(REFRESH_COOKIE)
    if not raw:
        clear_auth_cookies(response)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token is missing",
        )
    try:
        issued = await service.refresh(raw, client_ip(request))
    except HTTPException:
        clear_auth_cookies(response)
        raise
    _apply_session(response, issued)
    return MessageResponse(message="ok")


@router.post("/logout", response_model=MessageResponse)
async def logout(
    request: Request, response: Response, service: AuthServiceDep
) -> MessageResponse:
    await service.logout(request.cookies.get(REFRESH_COOKIE))
    clear_auth_cookies(response)
    return MessageResponse(message="ok")


@router.post("/forgot-password", response_model=MessageResponse)
async def forgot_password(
    data: ForgotPasswordRequest, request: Request, service: AuthServiceDep
) -> MessageResponse:
    return await service.forgot_password(data, client_ip(request))


@router.post("/resend-reset", response_model=MessageResponse)
async def resend_reset(
    data: ForgotPasswordRequest, request: Request, service: AuthServiceDep
) -> MessageResponse:
    return await service.resend_reset(data, client_ip(request))


@router.post("/reset-password", response_model=MessageResponse)
async def reset_password(
    data: ResetPasswordRequest, service: AuthServiceDep
) -> MessageResponse:
    return await service.reset_password(data)
