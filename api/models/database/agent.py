"""
Agent model - ĐƠN GIẢN, chỉ những field cần thiết
"""
from typing import Dict, Any, List
from sqlalchemy import Column, String, Boolean, Text, Float, ForeignKey, Index
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import JSONB

from models.database.base import BaseModel


class Agent(BaseModel):
    """
    Agent model simple - only the fields needed
    """
    
    __tablename__ = "agents"
    
    # Basic info
    name = Column(
        String(100),
        nullable=False,
        unique=True,
        index=True,
        comment="Tên agent: hr_specialist, finance_specialist, etc."
    )
    
    display_name = Column(
        String(200),
        nullable=False,
        comment="Tên hiển thị"
    )
    
    domain = Column(
        String(50),
        nullable=False,
        index=True,
        comment="Domain: hr, finance, it, general"
    )
    
    description = Column(
        Text,
        nullable=True,
        comment="Mô tả agent"
    )
    
    # Status
    is_enabled = Column(
        Boolean,
        nullable=False,
        default=False,  # SECURITY-FIRST: Mặc định TẮT
        index=True,
        comment="Agent có được bật không"
    )
    
    # Configuration - ĐƠN GIẢN
    capabilities = Column(
        JSONB,
        nullable=True,
        comment="Danh sách capabilities: ['policy_analysis', 'compensation_queries']"
    )
    
    confidence_threshold = Column(
        Float,
        nullable=False,
        default=0.7,
        comment="Ngưỡng confidence"
    )
    
    # Provider
    default_provider_id = Column(
        String(36),
        ForeignKey("providers.id"),
        nullable=True,
        index=True,
        comment="Provider mặc định cho agent"
    )
    
    default_model = Column(
        String(100),
        nullable=False,
        default="gemini-2.0-flash",
        comment="Model mặc định"
    )
    
    # Relationships
    provider = relationship("Provider", foreign_keys=[default_provider_id])
    agent_tools = relationship("AgentTool", back_populates="agent", cascade="all, delete-orphan")
    
    __table_args__ = (
        Index('idx_agent_domain_enabled', 'domain', 'is_enabled'),
    )
    
    def get_capabilities_list(self) -> List[str]:
        """Lấy list capabilities"""
        return self.capabilities or []
    
    def get_enabled_tools(self) -> List[str]:
        """Lấy tools đang enabled cho agent này"""
        return [at.tool.name for at in self.agent_tools if at.is_enabled and at.tool.is_enabled]
    
    def __repr__(self) -> str:
        return f"<Agent(name='{self.name}', domain='{self.domain}', enabled={self.is_enabled})>"


class AgentTool(BaseModel):
    """
    Agent-Tool relationship - ĐƠNG GIẢN
    1 Agent có NHIỀU Tools
    """
    
    __tablename__ = "agent_tools"
    
    agent_id = Column(
        String(36),
        ForeignKey("agents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="ID của agent"
    )
    
    tool_id = Column(
        String(36),
        ForeignKey("tools.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="ID của tool"
    )
    
    is_enabled = Column(
        Boolean,
        nullable=False,
        default=True,
        comment="Tool có enabled cho agent này không"
    )
    
    # Relationships
    agent = relationship("Agent", back_populates="agent_tools")
    tool = relationship("Tool")
    
    __table_args__ = (
        Index('idx_agent_tool_unique', 'agent_id', 'tool_id', unique=True),
        Index('idx_agent_tool_enabled', 'agent_id', 'is_enabled'),
    )
    
    def __repr__(self) -> str:
        return f"<AgentTool(agent_id={self.agent_id}, tool_id={self.tool_id}, enabled={self.is_enabled})>" 