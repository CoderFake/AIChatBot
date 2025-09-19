"""
Redesigned User model
"""
from typing import List, Dict, Any, Optional
from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey, UniqueConstraint, Index
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.sql import text
from utils.datetime_utils import CustomDateTime as datetime
from common.types import UserRole
from models.database.base import BaseModel


class User(BaseModel):
    
    __tablename__ = "users"
    
    username = Column(
        String(100),
        nullable=False,
        index=True,
        comment="Username for login"
    )
    
    email = Column(
        String(255),
        nullable=False,
        unique=True,
        index=True,
        comment="Email address"
    )
    
    hashed_password = Column(
        String(255),
        nullable=False,
        comment="Hashed password"
    )
    
    first_name = Column(
        String(100),
        nullable=False,
        comment="First name"
    )
    
    last_name = Column(
        String(100),
        nullable=False,
        comment="Last name"
    )
    
    role = Column(
        String(50),
        nullable=False,
        default="USER",
        index=True,
        comment="User role: MAINTAINER, ADMIN, DEPT_ADMIN, DEPT_MANAGER, USER"
    )
    
    tenant_id = Column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
        comment="Tenant ID"
    )
    
    department_id = Column(
        UUID(as_uuid=True),
        ForeignKey("departments.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="Department ID"
    )
    
    # Status fields
    is_active = Column(
        Boolean,
        nullable=False,
        default=True,
        index=True,
        comment="Whether user account is active"
    )
    
    __table_args__ = (
        UniqueConstraint('tenant_id', 'username', name='uq_user_tenant_username'),
    )
    is_verified = Column(
        Boolean,
        nullable=False,
        default=False,
        comment="Whether email is verified"
    )
    
    last_login = Column(
        DateTime(timezone=True),
        nullable=True,
        comment="Last login timestamp"
    )
    
    profile_data = Column(
        JSONB,
        nullable=True,
        comment="Additional profile information"
    )
    
    # Relationships
    tenant = relationship("Tenant", back_populates="users")
    department = relationship("Department", back_populates="users")
    permissions = relationship(
        "UserPermission",
        back_populates="user",
        cascade="all, delete-orphan",
        foreign_keys="UserPermission.user_id",
    )
    group_memberships = relationship(
        "UserGroupMembership",
        back_populates="user",
        cascade="all, delete-orphan",
        foreign_keys="UserGroupMembership.user_id",
    )
    chat_sessions = relationship("ChatSession", back_populates="user")
    documents = relationship(
        "Document",
        back_populates="uploaded_by_user",
        foreign_keys="Document.uploaded_by",
    )
    
    __table_args__ = (
        UniqueConstraint('username', name='uq_user_username'),
        UniqueConstraint('email', name='uq_user_email'),
        Index('idx_user_tenant_role', 'tenant_id', 'role'),
        Index('idx_user_dept_active', 'department_id', 'is_active'),
        Index('idx_user_role_active', 'role', 'is_active'),
    )
    
    def __repr__(self) -> str:
        return f"<User(id='{self.id}', username='{self.username}', role='{self.role}')>"
    
    def get_full_name(self) -> str:
        """Get user's full name"""
        return f"{self.first_name} {self.last_name}"
    
    def is_admin_role(self) -> bool:
        """Check if user has admin-level role"""
        return self.role in [UserRole.ADMIN.value, UserRole.DEPT_ADMIN.value]
    
    def can_manage_department(self) -> bool:
        """Check if user can manage department"""
        return self.role in [UserRole.ADMIN.value, UserRole.DEPT_ADMIN.value, UserRole.DEPT_MANAGER.value]


class TokenBlacklist(BaseModel):
    """
    Token blacklist for logout and security
    Optimized for fast lookup and auto-cleanup
    """
    
    __tablename__ = "token_blacklist"
    
    jti = Column(
        String(255),
        nullable=False,
        unique=True,
        index=True,
        comment="JWT Token ID (jti claim)"
    )
    
    token_type = Column(
        String(20),
        nullable=False,
        index=True,
        comment="Token type: access, refresh"
    )
    
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="User ID who owned the token"
    )
    
    expires_at = Column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
        comment="When token expires (for cleanup)"
    )
    
    reason = Column(
        String(50),
        nullable=False,
        default="logout",
        comment="Reason for blacklisting: logout, security, admin_revoke"
    )
    
    # Relationships
    user = relationship("User")
    
    __table_args__ = (
        Index('idx_blacklist_jti', 'jti'),
        Index('idx_blacklist_expires', 'expires_at'),
        Index('idx_blacklist_user_type', 'user_id', 'token_type'),
    )
    
    def __repr__(self) -> str:
        return f"<TokenBlacklist(jti='{self.jti}', type='{self.token_type}')>"
    
    @classmethod
    def is_token_blacklisted(cls, jti: str) -> bool:
        """
        Check if token is blacklisted
        This will be implemented in service layer
        """
        pass
    
    @classmethod
    def cleanup_expired_tokens(cls):
        """
        Cleanup expired tokens from blacklist
        This will be implemented in service layer
        """
        pass