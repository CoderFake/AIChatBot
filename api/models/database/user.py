# api/models/database/user.py
"""
Enhanced User model with multi-tenant and department support
Comprehensive role-based access control system
"""
from typing import List, Dict, Any, Optional
from sqlalchemy import Column, String, Boolean, Text, DateTime, Integer, ForeignKey, UniqueConstraint, Index
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.sql import text
from utils.datetime_utils import CustomDateTime as datetime

from models.database.base import BaseModel
from models.database.types import RoleTypes

class User(BaseModel):
    """
    Enhanced User model with multi-tenant and department support
    Supports hierarchical roles and permissions
    """
    
    __tablename__ = "users"
    
    # Basic information
    username = Column(
        String(100),
        nullable=False,
        index=True,
        comment="Username for login"
    )
    
    email = Column(
        String(255),
        nullable=False,
        index=True,
        comment="Email address"
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
    
    hashed_password = Column(
        String(255),
        nullable=False,
        comment="Hashed password"
    )
    
    # Tenant & Department relationships
    tenant_id = Column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Tenant ID"
    )
    
    department_id = Column(
        UUID(as_uuid=True),
        ForeignKey("departments.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Department ID"
    )
    
    # Role system
    role = Column(
        String(50),
        nullable=False,
        default="USER",
        index=True,
        comment="System role: MAINTAINER, ADMIN, DEPT_ADMIN, DEPT_MANAGER, USER"
    )
    
    # Status fields
    is_active = Column(
        Boolean,
        nullable=False,
        default=True,
        server_default=text("TRUE"),
        comment="Whether user is active"
    )
    
    is_verified = Column(
        Boolean,
        nullable=False,
        default=False,
        server_default=text("FALSE"),
        comment="Whether email is verified"
    )
    
    is_superuser = Column(
        Boolean,
        nullable=False,
        default=False,
        server_default=text("FALSE"),
        comment="Whether user has superuser privileges"
    )
    
    # Relationships
    tenant = relationship("Tenant", back_populates="users")
    department = relationship("Department", back_populates="users")
    
    permissions = relationship(
        "UserPermission",
        back_populates="user",
        cascade="all, delete-orphan"
    )
    
    group_memberships = relationship(
        "UserGroupMembership",
        back_populates="user",
        cascade="all, delete-orphan"
    )
    
    documents = relationship(
        "Document",
        back_populates="uploaded_by_user",
        foreign_keys="Document.uploaded_by"
    )
    
    __table_args__ = (
        UniqueConstraint('tenant_id', 'username', name='uq_tenant_user'),
        UniqueConstraint('tenant_id', 'email', name='uq_tenant_email'),
        Index('idx_user_role_dept', 'role', 'department_id'),
        Index('idx_user_active', 'is_active'),
    )
    
    @property
    def display_name(self) -> str:
        """Get user's display name"""
        return f"{self.first_name} {self.last_name}".strip()
    
    def is_maintainer(self) -> bool:
        """Check if user is maintainer (all tenant access)"""
        return self.role.upper() == RoleTypes.MAINTAINER.value or self.is_superuser
    
    def is_admin(self) -> bool:
        """Check if user is tenant admin"""
        return self.role.upper() == RoleTypes.ADMIN.value or self.is_maintainer()
    
    def is_department_admin(self) -> bool:
        """Check if user is department admin"""
        return self.role.upper() in [RoleTypes.DEPT_ADMIN.value, RoleTypes.ADMIN.value] or self.is_maintainer()
    
    def is_department_manager(self) -> bool:
        """Check if user is department manager"""
        return self.role.upper() in [RoleTypes.DEPT_MANAGER.value, RoleTypes.DEPT_ADMIN.value, RoleTypes.ADMIN.value] or self.is_maintainer()
    
    def can_access_department(self, department_id: str) -> bool:
        """Check if user can access specific department"""
        if self.is_admin():
            return True
        return str(self.department_id) == department_id
    
    def can_manage_tenant(self) -> bool:
        """Check if user can manage tenant-level settings"""
        return self.is_admin()
    
    def can_manage_department(self, department_id: str = None) -> bool:
        """Check if user can manage department settings"""
        if self.is_admin():
            return True
        if department_id is None:
            department_id = str(self.department_id)
        return self.is_department_admin() and str(self.department_id) == department_id
    
    def get_accessible_departments(self) -> List[str]:
        """Get list of department IDs user can access"""
        if self.is_admin():
            return "ALL"
        return [str(self.department_id)]
    
    def to_dict(self, include_sensitive: bool = False) -> dict:
        """Convert user to dictionary with option for sensitive data"""
        data = super().to_dict()
        
        if not include_sensitive:
            sensitive_fields = ['hashed_password']
            for field in sensitive_fields:
                data.pop(field, None)
        
        data.update({
            'display_name': self.display_name,
            'accessible_departments': self.get_accessible_departments()
        })
        
        return data
    
    def __repr__(self) -> str:
        return f"<User(id={self.id}, username='{self.username}', role='{self.role}')>"