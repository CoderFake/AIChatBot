from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_
from config.database import get_db
from typing import Dict
from services.auth.auth_service import AuthService
from services.auth.validate_permission import ValidatePermission
from utils.jwt_utils import JWTManager
from utils.request_utils import get_tenant_identifier_from_request
from services.send_mail.invite_service import InviteService
from services.send_mail.reset_service import ResetService
from models.database.user import User
from utils.password_utils import verify_password, hash_password
from api.v1.middleware.middleware import RequireOnlyMaintainer
from models.schemas.request.auth import (
    LoginRequest,
    LogoutRequest,
    MaintainerInviteRequest,
    AcceptInviteRequest,
    ForgotPasswordRequest,
    ResetPasswordRequest,
    ChangePasswordRequest,
    RefreshTokenRequest,
)
from models.schemas.responses.auth import (
    LoginResponse,
    LogoutResponse,
    InviteResponse,
    OperationResult,
    RefreshTokenResponse,
)
from utils.logging import get_logger
from utils.datetime_utils import DateTimeManager

logger = get_logger(__name__)
router = APIRouter()
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

    tenant_id = path_tenant_id or payload.tenant_id or sub_domain

    user_data = await service.authenticate_user(
        payload.username,
        payload.password,
        tenant_id=tenant_id,
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
    

@router.post("/refresh-token", response_model=RefreshTokenResponse)
async def refresh(payload: RefreshTokenRequest, db: AsyncSession = Depends(get_db)):
    try:
        refresh_payload = JWTManager.verify_token_type(payload.refresh_token, "refresh")
        user_id = refresh_payload.get("user_id")
        role = refresh_payload.get("role", "USER")
        if not user_id:
            raise ValueError("Invalid refresh token")
    except Exception:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")

    access_token = JWTManager.encode_token({"user_id": user_id, "role": role}, token_type="access")
    return RefreshTokenResponse(access_token=access_token, expires_in=0)


@router.post(
    "/logout",
    response_model=LogoutResponse,
    operation_id="auth_logout",
    summary="User logout",
)
async def logout(
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
    "/validate-invite-token",
    summary="Validate invite token and get user info"
)
async def validate_invite_token(request: Dict[str, str], db: AsyncSession = Depends(get_db)):
    """Validate invite token and return user info without accepting"""
    try:
        token = request.get("token")
        if not token:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Token is required"
            )

        service = InviteService(db)
        user_info = await service.validate_invite_token(token)

        if not user_info:
            token_hash = service._hash_token(token)
            result = await db.execute(
                select(UserActionToken).where(
                    UserActionToken.token_hash == token_hash,
                    UserActionToken.token_type.in_(['invite', 'invite_new_user', 'invite_existing_user'])
                )
            )
            token_record = result.scalar_one_or_none()

            if not token_record:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid invite token"
                )
            elif token_record.used:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invite token has already been used"
                )
            elif token_record.expires_at and token_record.expires_at <= DateTimeManager._now():
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invite token has expired"
                )
            else:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid invite token"
                )

        return user_info

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Validate invite token failed: {e}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid invite token")


@router.post(
    "/accept-invite",
    response_model=OperationResult,
    summary="Accept invite with required new password"
)
async def accept_invite(request: Dict[str, str], db: AsyncSession = Depends(get_db)):
    token = request.get("token")
    new_password = request.get("new_password")

    if not token or not new_password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Token and new_password are required"
        )

    service = InviteService(db)
    ok = await service.accept_invite(token, new_password)
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

    sub_domain, path_tenant_id = get_tenant_identifier_from_request(request)
    tenant_id = payload.tenant_id or path_tenant_id or sub_domain

    success = await service.request_password_reset(payload.username_or_email, request, tenant_id)
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



@router.get(
    "/me",
    response_model=dict,
    operation_id="auth_get_profile", 
    summary="Get current user profile"
)
async def get_current_user_profile(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db)
):
    """
    Get current user profile information
    Uses token validation to ensure user is authenticated and active
    """
    try:
        payload = JWTManager.decode_token(credentials.credentials)
        user_id = payload.get("user_id") or payload.get("sub")
        
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token"
            )
        
        result = await db.execute(
            select(User).where(
                User.id == user_id,
                User.is_active == True,
                User.is_deleted == False
            )
        )
        user = result.scalar_one_or_none()
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found or inactive"
            )
        
        return {
            "user_id": str(user.id),
            "username": user.username,
            "email": user.email,
            "full_name": user.get_full_name() if hasattr(user, 'get_full_name') else f"{user.first_name or ''} {user.last_name or ''}".strip(),
            "role": user.role,
            "tenant_id": str(user.tenant_id) if user.tenant_id else None,
            "department_id": str(user.department_id) if user.department_id else None,
            "is_verified": user.is_verified,
            "last_login": user.last_login.isoformat() if user.last_login else None,
            "created_at": user.created_at.isoformat() if user.created_at else None,
            "force_password_change": getattr(user, 'force_password_change', False)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get user profile: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token"
        )