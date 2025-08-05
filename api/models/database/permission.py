"""
Enhanced permission system with role-based access control
Supports tenant, department, and user-level permissions
"""
from sqlalchemy import Column, String, Boolean, Text, DateTime, ForeignKey, UniqueConstraint, Index
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.sql import text

from models.database.base import BaseModel


class Permission(BaseModel):
    """
    Permission definitions for the system
    Granular permissions for different actions and resources
    """
    
    __tablename__ = "permissions"
    
    permission_code = Column(
        String(100),
        nullable=False,
        unique=True,
        index=True,
        comment="Unique permission code"
    )
    
    permission_name = Column(
        String(200),
        nullable=False,
        comment="Permission display name"
    )
    
    description = Column(
        Text,
        nullable=True,
        comment="Permission description"
    )
    
    resource_type = Column(
        String(50),
        nullable=False,
        index=True,
        comment="Resource type: document, tool, config, user"
    )
    
    action = Column(
        String(50),
        nullable=False,
        index=True,
        comment="Action: read, write, delete, admin"
    )
    
    is_system = Column(
        Boolean,
        nullable=False,
        default=False,
        comment="System permission that cannot be deleted"
    )
    
    # Relationships
    user_permissions = relationship(
        "UserPermission",
        back_populates="permission",
        cascade="all, delete-orphan"
    )
    
    group_permissions = relationship(
        "GroupPermission",
        back_populates="permission",
        cascade="all, delete-orphan"
    )
    
    __table_args__ = (
        Index('idx_permission_resource_action', 'resource_type', 'action'),
    )
    
    def __repr__(self) -> str:
        return f"<Permission(code='{self.permission_code}', resource='{self.resource_type}')>"


class Group(BaseModel):
    """
    Groups for organizing users and permissions
    Department-based and role-based grouping
    """
    
    __tablename__ = "groups"
    
    group_code = Column(
        String(100),
        nullable=False,
        unique=True,
        index=True,
        comment="Unique group code"
    )
    
    group_name = Column(
        String(200),
        nullable=False,
        comment="Group display name"
    )
    
    description = Column(
        Text,
        nullable=True,
        comment="Group description"
    )
    
    group_type = Column(
        String(50),
        nullable=False,
        index=True,
        comment="Group type: DEPARTMENT, ROLE, CUSTOM"
    )
    
    department_id = Column(
        UUID(as_uuid=True),
        ForeignKey("departments.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
        comment="Department ID if department-specific group"
    )
    
    is_system = Column(
        Boolean,
        nullable=False,
        default=False,
        comment="System group that cannot be deleted"
    )
    
    settings = Column(
        JSONB,
        nullable=True,
        comment="Group settings"
    )
    
    # Relationships
    permissions = relationship(
        "GroupPermission",
        back_populates="group",
        cascade="all, delete-orphan"
    )
    
    members = relationship(
        "UserGroupMembership",
        back_populates="group",
        cascade="all, delete-orphan"
    )
    
    __table_args__ = (
        Index('idx_group_type_dept', 'group_type', 'department_id'),
    )
    
    def __repr__(self) -> str:
        return f"<Group(code='{self.group_code}', type='{self.group_type}')>"


class UserPermission(BaseModel):
    """
    Direct user permissions
    Individual permissions assigned to users
    """
    
    __tablename__ = "user_permissions"
    
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="User ID"
    )
    
    permission_id = Column(
        UUID(as_uuid=True),
        ForeignKey("permissions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Permission ID"
    )
    
    granted_by = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        comment="User who granted this permission"
    )
    
    expires_at = Column(
        DateTime(timezone=True),
        nullable=True,
        comment="Permission expiration timestamp"
    )
    
    conditions = Column(
        JSONB,
        nullable=True,
        comment="Conditions for this permission"
    )
    
    # Relationships
    user = relationship("User", back_populates="permissions", foreign_keys=[user_id])
    permission = relationship("Permission", back_populates="user_permissions")
    granted_by_user = relationship("User", foreign_keys=[granted_by])
    
    __table_args__ = (
        UniqueConstraint('user_id', 'permission_id', name='uq_user_permission'),
        Index('idx_user_permission_expires', 'expires_at'),
    )
    
    def __repr__(self) -> str:
        return f"<UserPermission(user_id='{self.user_id}', permission_id='{self.permission_id}')>"


class GroupPermission(BaseModel):
    """
    Group permissions
    Permissions assigned to groups
    """
    
    __tablename__ = "group_permissions"
    
    group_id = Column(
        UUID(as_uuid=True),
        ForeignKey("groups.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Group ID"
    )
    
    permission_id = Column(
        UUID(as_uuid=True),
        ForeignKey("permissions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Permission ID"
    )
    
    granted_by = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        comment="User who granted this permission"
    )
    
    conditions = Column(
        JSONB,
        nullable=True,
        comment="Conditions for this permission"
    )
    
    # Relationships
    group = relationship("Group", back_populates="permissions")
    permission = relationship("Permission", back_populates="group_permissions")
    
    __table_args__ = (
        UniqueConstraint('group_id', 'permission_id', name='uq_group_permission'),
    )
    
    def __repr__(self) -> str:
        return f"<GroupPermission(group_id='{self.group_id}', permission_id='{self.permission_id}')>"


class UserGroupMembership(BaseModel):
    """
    User group membership
    Many-to-many relationship between users and groups
    """
    
    __tablename__ = "user_group_memberships"
    
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="User ID"
    )
    
    group_id = Column(
        UUID(as_uuid=True),
        ForeignKey("groups.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Group ID"
    )
    
    added_by = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        comment="User who added this membership"
    )
    
    role_in_group = Column(
        String(50),
        nullable=False,
        default="MEMBER",
        comment="Role in group: MEMBER, ADMIN"
    )
    
    expires_at = Column(
        DateTime(timezone=True),
        nullable=True,
        comment="Membership expiration timestamp"
    )
    
    # Relationships
    user = relationship("User", back_populates="group_memberships", foreign_keys=[user_id])
    group = relationship("Group", back_populates="members")
    added_by_user = relationship("User", foreign_keys=[added_by])
    
    __table_args__ = (
        UniqueConstraint('user_id', 'group_id', name='uq_user_group'),
        Index('idx_membership_expires', 'expires_at'),
    )
    
    def __repr__(self) -> str:
        return f"<UserGroupMembership(user_id='{self.user_id}', group_id='{self.group_id}')>"