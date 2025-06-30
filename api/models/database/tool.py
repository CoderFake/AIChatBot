"""
Tool model để quản lý tools trong hệ thống
Database-driven approach để tránh hard code
"""
from typing import Dict, Any, Optional, List
from sqlalchemy import Column, String, Boolean, Text, Index
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import JSONB

from models.database.base import BaseModel


class Tool(BaseModel):
    """
    Tool model để quản lý tools trong hệ thống
    Thay thế approach hard code bằng database-driven
    """
    
    __tablename__ = "tools"
    
    # Basic info
    name = Column(
        String(100),
        nullable=False,
        unique=True,
        index=True,
        comment="Tên tool duy nhất"
    )
    
    display_name = Column(
        String(200),
        nullable=False,
        comment="Tên hiển thị của tool"
    )
    
    description = Column(
        Text,
        nullable=True,
        comment="Mô tả chức năng của tool"
    )
    
    category = Column(
        String(50),
        nullable=False,
        index=True,
        comment="Danh mục tool: web_tools, document_tools, calculation_tools, etc."
    )
    
    # Configuration
    tool_config = Column(
        JSONB,
        nullable=True,
        comment="Cấu hình tool: parameters, limits, endpoints, etc."
    )
    
    implementation_class = Column(
        String(255),
        nullable=True,
        comment="Python class path để implement tool"
    )
    
    # Access control
    is_enabled = Column(
        Boolean,
        nullable=False,
        default=True,
        index=True,
        comment="Tool có được bật không"
    )
    
    is_system = Column(
        Boolean,
        nullable=False,
        default=False,
        comment="Tool hệ thống không thể xóa"
    )
    
    usage_limits = Column(
        JSONB,
        nullable=True,
        comment="Giới hạn sử dụng: calls_per_hour, max_concurrent, etc."
    )
    
    departments_allowed = Column(
        JSONB,
        nullable=True,
        comment="Danh sách departments được phép dùng tool này"
    )
    
    # Metadata
    version = Column(
        String(20),
        nullable=False,
        default="1.0.0",
        comment="Phiên bản tool"
    )
    
    requirements = Column(
        JSONB,
        nullable=True,
        comment="Yêu cầu: dependencies, permissions, etc."
    )
    
    documentation_url = Column(
        String(500),
        nullable=True,
        comment="Link đến tài liệu sử dụng tool"
    )
    
    # Relationships
    tool_permissions = relationship(
        "ToolPermission",
        back_populates="tool",
        cascade="all, delete-orphan"
    )
    
    agent_tools = relationship(
        "AgentTool",
        back_populates="tool",
        cascade="all, delete-orphan"
    )
    
    __table_args__ = (
        Index('idx_tool_category_enabled', 'category', 'is_enabled'),
        Index('idx_tool_enabled', 'is_enabled'),
    )
    
    def is_available_for_department(self, department: str) -> bool:
        """Kiểm tra tool có khả dụng cho department không"""
        if not self.is_enabled:
            return False
        
        if not self.departments_allowed:
            return True 
        
        return department.lower() in [dept.lower() for dept in self.departments_allowed]
    
    def get_usage_limit(self, limit_type: str) -> Optional[int]:
        """Lấy giới hạn sử dụng cụ thể"""
        if not self.usage_limits:
            return None
        return self.usage_limits.get(limit_type)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        data = super().to_dict()
        data.update({
            'permissions_required': [tp.permission.permission_name for tp in self.tool_permissions if tp.is_enabled],
            'departments_count': len(self.departments_allowed) if self.departments_allowed else 0,
            'has_limits': bool(self.usage_limits)
        })
        return data
    
    def __repr__(self) -> str:
        return f"<Tool(name='{self.name}', category='{self.category}', enabled={self.is_enabled})>" 