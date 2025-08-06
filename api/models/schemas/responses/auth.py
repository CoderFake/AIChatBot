
"""
Authentication response schemas
"""
from typing import Optional, List
from pydantic import BaseModel


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


class LoginResponse(BaseModel):
    """Login response schema"""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserInfoSchema


class RefreshTokenResponse(BaseModel):
    """Refresh token response schema"""
    access_token: str
    token_type: str = "bearer"
    expires_in: int


class LogoutResponse(BaseModel):
    """Logout response schema"""
    message: str = "Logged out successfully"


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