"""
Tool model - ĐƠN GIẢN, chỉ những field cần thiết
"""
from typing import Dict, Any, List
from sqlalchemy import Column, String, Boolean, Text, Index
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import JSONB

from models.database.base import BaseModel


class Tool(BaseModel):
    """
    Tool model đơn giản - chỉ field cần thiết
    """
    
    __tablename__ = "tools"
    
    # Basic info
    name = Column(
        String(100),
        nullable=False,
        unique=True,
        index=True,
        comment="Tên tool: web_search, document_search, etc."
    )
    
    display_name = Column(
        String(200),
        nullable=False,
        comment="Tên hiển thị"
    )
    
    description = Column(
        Text,
        nullable=True,
        comment="Mô tả tool"
    )
    
    category = Column(
        String(50),
        nullable=False,
        index=True,
        comment="Danh mục: web_tools, document_tools, calculation_tools"
    )
    
    # Status
    is_enabled = Column(
        Boolean,
        nullable=False,
        default=False,
        index=True,
        comment="Tool có được bật không"
    )
    
    # Configuration
    tool_config = Column(
        JSONB,
        nullable=True,
        comment="Config đơn giản: {timeout: 30, max_results: 10}"
    )
    
    # Relationships
    agent_tools = relationship("AgentTool", back_populates="tool")
    
    __table_args__ = (
        Index('idx_tool_category_enabled', 'category', 'is_enabled'),
    )
    
    def __repr__(self) -> str:
        return f"<Tool(name='{self.name}', category='{self.category}', enabled={self.is_enabled})>" 