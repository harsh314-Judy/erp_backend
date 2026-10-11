from fastapi import APIRouter, status

from app.api.dependencies import AuthServiceDep
from app.api.routes.auth.auth_schemas import (
    ForgotPasswordRequest,
    ForgotPasswordResponse,
    InviteCreate,
    InviteRead,
    LoginRequest,
    RefreshRequest,
    ResetPasswordRequest,
    SignupRequest,
    TokenResponse,
)
from app.api.routes.user.user_schemas import UserRead
from app.api.schemas.common import MessageResponse

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/invites", response_model=InviteRead, status_code=status.HTTP_201_CREATED)
async def create_invite(data: InviteCreate, service: AuthServiceDep) -> InviteRead:
    return await service.create_invite(data)


@router.post("/signup", response_model=UserRead, status_code=status.HTTP_201_CREATED)
async def signup(data: SignupRequest, service: AuthServiceDep) -> UserRead:
    return await service.signup(data)


@router.post("/login", response_model=TokenResponse)
async def login(data: LoginRequest, service: AuthServiceDep) -> TokenResponse:
    return await service.login(data)


@router.post("/refresh", response_model=TokenResponse)
async def refresh(data: RefreshRequest, service: AuthServiceDep) -> TokenResponse:
    return await service.refresh(data)


@router.post("/forgot-password", response_model=ForgotPasswordResponse)
async def forgot_password(
    data: ForgotPasswordRequest, service: AuthServiceDep
) -> ForgotPasswordResponse:
    return await service.forgot_password(data)


@router.post("/reset-password", response_model=MessageResponse)
async def reset_password(
    data: ResetPasswordRequest, service: AuthServiceDep
) -> MessageResponse:
    return await service.reset_password(data)
