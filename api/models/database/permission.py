# api/models/database/permission.py

from typing import List, Optional, Dict, Any
from sqlalchemy import Column, String, Boolean, Text, ForeignKey, Index, UniqueConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import JSONB

from models.database.base import BaseModel

class Permission(BaseModel):
    """
    Permission model định nghĩa các quyền trong hệ thống
    """
    
    __tablename__ = "permissions"
    
    permission_name = Column(
        String(100),
        nullable=False,
        unique=True,
        index=True,
        comment="Tên permission duy nhất"
    )
    
    display_name = Column(
        String(200),
        nullable=False,
        comment="Tên hiển thị permission"
    )
    
    description = Column(
        Text,
        nullable=True,
        comment="Mô tả chi tiết permission"
    )
    
    category = Column(
        String(50),
        nullable=False,
        index=True,
        comment="Danh mục: DOCUMENT, TOOL, ADMIN, DEPARTMENT"
    )
    
    resource_type = Column(
        String(50),
        nullable=True,
        comment="Loại resource: collection, tool, function"
    )
    
    actions = Column(
        JSONB,
        nullable=True,
        comment="Các actions được phép: read, write, delete, execute"
    )
    
    conditions = Column(
        JSONB,
        nullable=True,
        comment="Điều kiện áp dụng permission"
    )
    
    is_system = Column(
        Boolean,
        nullable=False,
        default=False,
        comment="Permission hệ thống không thể xóa"
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
        Index('idx_permission_category', 'category'),
        Index('idx_permission_resource', 'resource_type'),
    )
    
    def __repr__(self) -> str:
        return f"<Permission(name='{self.permission_name}', category='{self.category}')>"

class Group(BaseModel):
    """
    Group model cho phân quyền theo nhóm
    """
    
    __tablename__ = "groups"
    
    group_name = Column(
        String(100),
        nullable=False,
        unique=True,
        index=True,
        comment="Tên group duy nhất"
    )
    
    display_name = Column(
        String(200),
        nullable=False,
        comment="Tên hiển thị group"
    )
    
    description = Column(
        Text,
        nullable=True,
        comment="Mô tả group"
    )
    
    group_type = Column(
        String(50),
        nullable=False,
        index=True,
        comment="Loại group: DEPARTMENT, ROLE, CUSTOM"
    )
    
    department = Column(
        String(100),
        nullable=True,
        index=True,
        comment="Department liên quan (nếu có)"
    )
    
    is_system = Column(
        Boolean,
        nullable=False,
        default=False,
        comment="Group hệ thống không thể xóa"
    )
    
    settings = Column(
        JSONB,
        nullable=True,
        comment="Cài đặt group"
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
        Index('idx_group_type_dept', 'group_type', 'department'),
    )
    
    def __repr__(self) -> str:
        return f"<Group(name='{self.group_name}', type='{self.group_type}')>"

class UserPermission(BaseModel):
    """
    User permission mapping - quyền trực tiếp của user
    """
    
    __tablename__ = "user_permissions"
    
    user_id = Column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="ID của user"
    )
    
    permission_id = Column(
        String(36),
        ForeignKey("permissions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="ID của permission"
    )
    
    granted_by = Column(
        String(36),
        nullable=True,
        comment="User ID của người cấp quyền"
    )
    
    expires_at = Column(
        nullable=True,
        comment="Thời điểm hết hạn quyền"
    )
    
    conditions = Column(
        JSONB,
        nullable=True,
        comment="Điều kiện áp dụng cho permission này"
    )
    
    # Relationships
    user = relationship("User", back_populates="permissions")
    permission = relationship("Permission", back_populates="user_permissions")
    
    __table_args__ = (
        UniqueConstraint('user_id', 'permission_id', name='uq_user_permission'),
        Index('idx_user_permission_expires', 'expires_at'),
    )
    
    def __repr__(self) -> str:
        return f"<UserPermission(user_id='{self.user_id}', permission='{self.permission.permission_name}')>"

class GroupPermission(BaseModel):
    """
    Group permission mapping - quyền của group
    """
    
    __tablename__ = "group_permissions"
    
    group_id = Column(
        String(36),
        ForeignKey("groups.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="ID của group"
    )
    
    permission_id = Column(
        String(36),
        ForeignKey("permissions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="ID của permission"
    )
    
    granted_by = Column(
        String(36),
        nullable=True,
        comment="User ID của người cấp quyền"
    )
    
    conditions = Column(
        JSONB,
        nullable=True,
        comment="Điều kiện áp dụng cho permission này"
    )
    
    # Relationships
    group = relationship("Group", back_populates="permissions")
    permission = relationship("Permission", back_populates="group_permissions")
    
    __table_args__ = (
        UniqueConstraint('group_id', 'permission_id', name='uq_group_permission'),
    )
    
    def __repr__(self) -> str:
        return f"<GroupPermission(group='{self.group.group_name}', permission='{self.permission.permission_name}')>"

class UserGroupMembership(BaseModel):
    """
    User group membership - thành viên của group
    """
    
    __tablename__ = "user_group_memberships"
    
    user_id = Column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="ID của user"
    )
    
    group_id = Column(
        String(36),
        ForeignKey("groups.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="ID của group"
    )
    
    added_by = Column(
        String(36),
        nullable=True,
        comment="User ID của người thêm vào group"
    )
    
    role_in_group = Column(
        String(50),
        nullable=False,
        default="MEMBER",
        comment="Vai trò trong group: MEMBER, ADMIN"
    )
    
    expires_at = Column(
        nullable=True,
        comment="Thời điểm hết hạn membership"
    )
    
    # Relationships
    user = relationship("User", back_populates="group_memberships")
    group = relationship("Group", back_populates="members")
    
    __table_args__ = (
        UniqueConstraint('user_id', 'group_id', name='uq_user_group'),
        Index('idx_membership_expires', 'expires_at'),
    )
    
    def __repr__(self) -> str:
        return f"<UserGroupMembership(user_id='{self.user_id}', group='{self.group.group_name}')>"

class ToolPermission(BaseModel):
    """
    Tool permission model - mapping giữa tool và permission
    """
    
    __tablename__ = "tool_permissions"
    
    tool_id = Column(
        String(36),
        ForeignKey("tools.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="ID của tool"
    )
    
    permission_id = Column(
        String(36),
        ForeignKey("permissions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Permission cần thiết để sử dụng tool"
    )
    
    is_enabled = Column(
        Boolean,
        nullable=False,
        default=True,
        comment="Permission mapping có được bật không"
    )
    
    conditions = Column(
        JSONB,
        nullable=True,
        comment="Điều kiện bổ sung cho permission này"
    )
    
    # Relationships
    tool = relationship("Tool", back_populates="tool_permissions")
    permission = relationship("Permission")
    
    __table_args__ = (
        UniqueConstraint('tool_id', 'permission_id', name='uq_tool_permission'),
    )
    
    def __repr__(self) -> str:
        return f"<ToolPermission(tool='{self.tool.name}', permission='{self.permission.permission_name}', enabled={self.is_enabled})>"