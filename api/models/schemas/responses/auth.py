from typing import Optional, List
from pydantic import BaseModel, Field


class UserInfoSchema(BaseModel):
    """User information schema"""
    user_id: str
    username: str
    email: str
    first_name: str
    last_name: str
    role: str
    tenant_id: Optional[str] = None
    department_id: Optional[str] = None
    department_name: Optional[str] = None
    tenant_name: Optional[str] = None
    is_active: bool
    created_at: Optional[str] = None
    last_login: Optional[str] = None
    permissions: List[str] = []


class TokenPairResponse(BaseModel):
    access_token: str = Field(..., description="JWT access token")
    refresh_token: str = Field(..., description="JWT refresh token")
    token_type: str = Field("bearer", description="Token type")


class LoginResponse(BaseModel):
    user_id: str
    username: str
    email: str
    full_name: Optional[str] = None
    role: str
    tenant_id: Optional[str] = None
    department_id: Optional[str] = None
    is_verified: bool
    last_login: Optional[str] = None
    first_login: bool = Field(..., description="True if first login") 
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshTokenResponse(BaseModel):
    """Refresh token response schema"""
    access_token: str
    token_type: str = "bearer"
    expires_in: int


class LogoutResponse(BaseModel):
    success: bool
    detail: str


class UserInfoResponse(BaseModel):
    """User information response schema"""
    user: UserInfoSchema


class ChangePasswordResponse(BaseModel):
    """Change password response schema"""
    message: str = "Password changed successfully"


class TokenValidationResponse(BaseModel):
    """Token validation response schema"""
    valid: bool
    user_id: Optional[str] = None
    role: Optional[str] = None
    expires_at: Optional[str] = None


class InviteResponse(BaseModel):
    """Invite response containing generated links"""
    links: List[str]


class UserProfileResponse(BaseModel):
    """User profile response schema"""
    user_id: str
    username: str
    email: str
    full_name: Optional[str] = None
    role: str
    tenant_id: Optional[str] = None
    department_id: Optional[str] = None
    is_verified: bool
    last_login: Optional[str] = None
    created_at: Optional[str] = None
    force_password_change: bool = False
    permissions: List[str] = []


class PasswordResetResponse(BaseModel):
    """Password reset request response schema"""
    success: bool
    message: str


class PasswordResetConfirmResponse(BaseModel):
    """Password reset confirmation response schema"""
    success: bool
    message: str


class OperationResult(BaseModel):
    success: bool = True
    detail: str = "OK"