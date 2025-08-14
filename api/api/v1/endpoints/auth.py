from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from config.database import get_db
from services.auth.auth_service import AuthService
from utils.jwt_utils import JWTManager
from models.schemas.request.auth import LoginRequest, LogoutRequest
from models.schemas.responses.auth import LoginResponse, LogoutResponse
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
async def login(payload: LoginRequest, db: AsyncSession = Depends(get_db)):
    service = AuthService(db)
    user_data = await service.authenticate_user(payload.username, payload.password)
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
