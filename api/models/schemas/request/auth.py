"""
Authentication request schemas
"""
from typing import Optional
from pydantic import BaseModel, EmailStr, Field, field_validator


class LoginRequest(BaseModel):
    username: str = Field(..., description="Username")
    password: str = Field(..., description="Password")
    tenant_id: Optional[str] = Field(None, description="Tenant ID for tenant-specific login")
    sub_domain: Optional[str] = Field(None, description="Subdomain for tenant identification")
    
    @field_validator('username')
    @classmethod
    def validate_username(cls, v):
        if not v or len(v.strip()) == 0:
            raise ValueError('Username cannot be empty')
        return v.strip()
    
    @field_validator('password')
    @classmethod
    def validate_password(cls, v):
        if not v or len(v) < 6:
            raise ValueError('Password must be at least 6 characters')
        return v


class RefreshTokenRequest(BaseModel):
    """Refresh token request schema"""
    refresh_token: str
    
    @field_validator('refresh_token')
    @classmethod
    def validate_refresh_token(cls, v):
        if not v or len(v.strip()) == 0:
            raise ValueError('Refresh token cannot be empty')
        return v.strip()


class LogoutRequest(BaseModel):
    token: str = Field(..., description="Bearer token to revoke")


class ChangePasswordRequest(BaseModel):
    """Change password request schema"""
    current_password: str
    new_password: str
    confirm_password: str
    
    @field_validator('new_password')
    @classmethod
    def validate_new_password(cls, v):
        if not v or len(v) < 6:
            raise ValueError('New password must be at least 6 characters')
        return v
    
    @field_validator('confirm_password')
    @classmethod
    def validate_confirm_password(cls, v, info):
        if 'new_password' in info.data and v != info.data['new_password']:
            raise ValueError('Passwords do not match')
        return v


class MaintainerInviteRequest(BaseModel):
    """Maintainer invites list of emails to become tenant admins"""
    tenant_id: Optional[str] = Field(None, description="Target tenant ID (optional for MAINTAINER invites)")
    emails: list[EmailStr] = Field(..., min_length=1)


class AcceptInviteRequest(BaseModel):
    token: str = Field(..., description="Opaque invite token")
    new_password: Optional[str] = Field(None, description="Optional new password to set on accept")


class ForgotPasswordRequest(BaseModel):
    username_or_email: str = Field(..., description="Username or email to send reset link")
    tenant_id: Optional[str] = Field(None, description="Tenant ID for tenant-specific password reset")


class PasswordResetRequest(BaseModel):
    """Password reset request schema"""
    email: EmailStr = Field(..., description="User email address")
    tenant_id: Optional[str] = Field(None, description="Tenant ID for multi-tenant systems")


class PasswordResetConfirmRequest(BaseModel):
    """Password reset confirmation request schema"""
    token: str = Field(..., description="Reset token from email")
    new_password: str = Field(..., min_length=6, description="New password")


class ResetPasswordRequest(BaseModel):
    token: str = Field(..., description="Opaque reset token")
    new_password: str = Field(..., min_length=6)
