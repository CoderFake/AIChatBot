from typing import Dict, Any, Optional
from sqlalchemy import Column, String, Boolean, Text, ForeignKey, Index
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import JSONB, UUID

from models.database.base import BaseModel


class Tool(BaseModel):
    """
    Global tool definitions
    Shared across all departments but configurable per department
    """
    
    __tablename__ = "tools"
    
    tool_name = Column(
        String(200),
        nullable=False,
        comment="Tool display name"
    )
    
    description = Column(
        Text,
        nullable=True,
        comment="Tool description and functionality"
    )
    
    category = Column(
        String(50),
        nullable=False,
        index=True,
        comment="Tool category: web_tools, document_tools, calculation_tools"
    )
    
    implementation_class = Column(
        String(255),
        nullable=True,
        comment="Python class path for tool implementation"
    )
    
    is_enabled = Column(
        Boolean,
        nullable=False,
        default=True,
        index=True,
        comment="Whether tool is globally enabled"
    )
    
    is_system = Column(
        Boolean,
        nullable=False,
        default=False,
        comment="System tool that cannot be deleted"
    )
    
    base_config = Column(
        JSONB,
        nullable=True,
        comment="Base tool configuration"
    )
    
    # Relationships
    department_configs = relationship(
        "DepartmentToolConfig",
        back_populates="tool",
        cascade="all, delete-orphan"
    )
    
    __table_args__ = (
        Index('idx_tool_enabled', 'is_enabled'),
        Index('idx_tool_category', 'category', 'is_enabled'),
    )
    
    def __repr__(self) -> str:
        return f"<Tool(id='{self.id}', name='{self.tool_name}')>"


class DepartmentToolConfig(BaseModel):
    """
    Department-level tool configuration
    Each department can enable/disable and configure tools
    """
    
    __tablename__ = "department_tool_configs"
    
    department_id = Column(
        UUID(as_uuid=True),
        ForeignKey("departments.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Department ID"
    )
    
    tool_id = Column(
        UUID(as_uuid=True),
        ForeignKey("tools.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Tool ID"
    )
    
    is_enabled = Column(
        Boolean,
        nullable=False,
        default=True,
        comment="Whether tool is enabled for this department"
    )
    
    config_data = Column(
        JSONB,
        nullable=True,
        comment="Department-specific tool configuration"
    )
    
    usage_limits = Column(
        JSONB,
        nullable=True,
        comment="Usage limits for this department"
    )
    
    configured_by = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        comment="User who configured this tool"
    )
    
    # Relationships
    department = relationship("Department", back_populates="tool_configs")
    tool = relationship("Tool", back_populates="department_configs")
    
    __table_args__ = (
        Index('idx_dept_tool_enabled', 'department_id', 'is_enabled'),
    )
    
    def __repr__(self) -> str:
        return f"<DepartmentToolConfig(id='{self.id}', dept_id={self.department_id}, tool_id={self.tool_id})>"