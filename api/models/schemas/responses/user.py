"""User response schemas"""
from typing import Optional
from pydantic import BaseModel, Field
from datetime import datetime


class UserResponse(BaseModel):
    """User response schema"""
    id: str
    username: str
    email: str
    full_name: Optional[str] = None
    role: str
    tenant_id: Optional[str] = None
    department_id: Optional[str] = None
    is_active: bool
    is_verified: bool
    last_login: Optional[str] = None
    created_at: Optional[str] = None


class UserListResponse(BaseModel):
    """Paginated user list response schema"""
    users: list[UserResponse]
    total: int
    page: int
    limit: int
    has_more: bool