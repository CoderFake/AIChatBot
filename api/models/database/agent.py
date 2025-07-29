from sqlalchemy import Column, String, Boolean, Text, ForeignKey, UniqueConstraint, Index
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.sql import text

from models.database.base import BaseModel


class Agent(BaseModel):
    """
    Agent definition for multi-agent RAG system
    Each department has exactly one agent
    """
    
    __tablename__ = "agents"
    
    agent_code = Column(
        String(50),
        nullable=False,
        unique=True,
        index=True,
        comment="Unique agent code"
    )
    
    agent_name = Column(
        String(100),
        nullable=False,
        comment="Agent display name"
    )
    
    description = Column(
        Text,
        nullable=False,
        comment="Agent description and capabilities"
    )
    
    is_enabled = Column(
        Boolean,
        nullable=False,
        default=True,
        comment="Whether agent is enabled"
    )
    
    is_system = Column(
        Boolean,
        nullable=False,
        default=False,
        comment="System agent that cannot be deleted"
    )
    
    department_id = Column(
        UUID(as_uuid=True),
        ForeignKey("departments.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
        comment="Department that owns this agent (1:1 relationship)"
    )
    
    provider_id = Column(
        UUID(as_uuid=True),
        ForeignKey("providers.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="Primary provider for this agent"
    )
    
    model_id = Column(
        UUID(as_uuid=True),
        ForeignKey("provider_models.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="Primary model for this agent"
    )
    
    # Relationships
    department = relationship("Department", back_populates="agent")
    provider = relationship("Provider")
    model = relationship("ProviderModel")
    
    tool_configs = relationship(
        "AgentToolConfig",
        back_populates="agent",
        cascade="all, delete-orphan"
    )
    
    __table_args__ = (
        Index('idx_agent_enabled', 'is_enabled'),
        Index('idx_agent_provider', 'provider_id'),
    )
    
    def __repr__(self) -> str:
        return f"<Agent(code='{self.agent_code}', department_id='{self.department_id}')>"


class AgentToolConfig(BaseModel):
    """
    Agent-tool mapping configuration
    Which tools each agent can access
    """
    
    __tablename__ = "agent_tool_configs"
    
    agent_id = Column(
        UUID(as_uuid=True),
        ForeignKey("agents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Agent ID"
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
        comment="Whether agent can use this tool"
    )
    
    config_data = Column(
        JSONB,
        nullable=True,
        comment="Agent-specific tool configuration"
    )
    
    agent = relationship("Agent", back_populates="tool_configs")
    tool = relationship("Tool")
    
    __table_args__ = (
        UniqueConstraint('agent_id', 'tool_id', name='uq_agent_tool'),
        Index('idx_agent_tool_enabled', 'agent_id', 'is_enabled'),
    )
    
    def __repr__(self) -> str:
        return f"<AgentToolConfig(agent_id={self.agent_id}, tool_id={self.tool_id})>"