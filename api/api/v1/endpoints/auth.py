from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_

from config.database import get_db
from services.auth.auth_service import AuthService
from utils.jwt_utils import JWTManager
from utils.request_utils import get_tenant_identifier_from_request
from services.send_mail.invite_service import InviteService
from services.send_mail.reset_service import ResetService
from models.database.user import User
from utils.password_utils import verify_password, hash_password
from api.api.v1.middleware.middleware import RequireOnlyMaintainer
from models.schemas.request.auth import (
    LoginRequest,
    LogoutRequest,
    MaintainerInviteRequest,
    AcceptInviteRequest,
    ForgotPasswordRequest,
    ResetPasswordRequest,
    ChangePasswordRequest,
)
from models.schemas.responses.auth import (
    LoginResponse,
    LogoutResponse,
    InviteResponse,
    OperationResult,
)
from utils.logging import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/auth", tags=["Authentication"])
security = HTTPBearer()


@router.post(
    "/login",
    response_model=LoginResponse,
    operation_id="auth_login",
    summary="User login",
)
async def login(payload: LoginRequest, request: Request, db: AsyncSession = Depends(get_db)):
    service = AuthService(db)
    sub_domain, path_tenant_id = get_tenant_identifier_from_request(request)
    user_data = await service.authenticate_user(
        payload.username,
        payload.password,
        tenant_id=path_tenant_id,
        sub_domain=sub_domain,
    )
    if not user_data:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    tokens = JWTManager.create_token_pair(user_data)

    return LoginResponse(
        user_id=user_data["user_id"],
        username=user_data["username"],
        email=user_data["email"],
        full_name=user_data.get("full_name"),
        role=user_data["role"],
        tenant_id=user_data.get("tenant_id"),
        department_id=user_data.get("department_id"),
        is_verified=user_data["is_verified"],
        last_login=user_data.get("last_login"),
        first_login=user_data["first_login"],
        access_token=tokens["access_token"],
        refresh_token=tokens["refresh_token"],
    )


@router.post(
    "/logout",
    response_model=LogoutResponse,
    operation_id="auth_logout",
    summary="User logout",
)
async def logout(
    req: LogoutRequest,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db),
):
    token = credentials.credentials
    try:
        payload = JWTManager.decode_token(token)
        jti = payload.get("jti")
        user_id = payload.get("user_id") or payload.get("sub")
        if not jti or not user_id:
            raise ValueError("Invalid token payload")
    except Exception as e:
        logger.error(f"Logout token decode error: {e}")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

    service = AuthService(db)
    success = await service.logout_user(user_id=user_id, jti=jti, token_type=payload.get("type", "access"))
    if not success:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Logout failed")

    return LogoutResponse(success=True, detail="Logged out successfully")


@router.post(
    "/maintainer/invite",
    response_model=InviteResponse,
    summary="Maintainer invites tenant admins"
)
async def maintainer_invite(
    payload: MaintainerInviteRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user_ctx: dict = Depends(RequireOnlyMaintainer()),
):
    service = InviteService(db)
    links = await service.invite_admins(payload.tenant_id, [str(e) for e in payload.emails], request)
    return InviteResponse(links=links)


@router.post(
    "/accept-invite",
    response_model=OperationResult,
    summary="Accept invite with optional new password"
)
async def accept_invite(payload: AcceptInviteRequest, db: AsyncSession = Depends(get_db)):
    service = InviteService(db)
    ok = await service.accept_invite(payload.token, payload.new_password)
    if not ok:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or used invite token")
    return OperationResult(success=True, detail="Invite accepted")


@router.post(
    "/forgot-password",
    response_model=OperationResult,
    summary="Request password reset link"
)
async def forgot_password(payload: ForgotPasswordRequest, request: Request, db: AsyncSession = Depends(get_db)):
    service = ResetService(db)
    q = select(User).where(
        or_(User.username == payload.username_or_email, User.email == payload.username_or_email),
        User.is_active == True,
        User.is_deleted == False,
    )
    result = await db.execute(q)
    user = result.scalar_one_or_none()
    if not user:
        return OperationResult(success=True, detail="If account exists, an email has been sent")
    await service.send_reset_email(user, request)
    return OperationResult(success=True, detail="If account exists, an email has been sent")


@router.post(
    "/reset-password",
    response_model=OperationResult,
    summary="Reset password with token"
)
async def reset_password(payload: ResetPasswordRequest, db: AsyncSession = Depends(get_db)):
    service = ResetService(db)
    ok = await service.reset_password(payload.token, payload.new_password)
    if not ok:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired reset token")
    return OperationResult(success=True, detail="Password has been reset")


@router.post(
    "/change-password",
    response_model=OperationResult,
    summary="Change password for current user"
)
async def change_password(
    payload: ChangePasswordRequest,
    db: AsyncSession = Depends(get_db),
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    try:
        payload_jwt = JWTManager.decode_token(credentials.credentials)
        user_id = payload_jwt.get("user_id") or payload_jwt.get("sub")
        if not user_id:
            raise ValueError("Invalid token payload")
    except Exception:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    if not verify_password(payload.current_password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Current password is incorrect")
    user.hashed_password = hash_password(payload.new_password)
    await db.commit()
    return OperationResult(success=True, detail="Password changed successfully")
