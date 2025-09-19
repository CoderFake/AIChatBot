from typing import List, Dict, Any, Optional
from sqlalchemy import Column, String, Boolean, Text, ForeignKey, Index, UniqueConstraint, Integer, Float
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.sql import text

from models.database.base import BaseModel

from models.database.tenant import Department

class Agent(BaseModel):
    """
    Agent definition for multi-agent RAG system
    Each department has exactly one agent
    """
    
    __tablename__ = "agents"
    
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

    tenant_id = Column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Tenant owner of this agent"
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
        UniqueConstraint('tenant_id', 'agent_name', name='uq_agent_tenant_name'),
    )
    
    def __repr__(self) -> str:
        return f"<Agent(id='{self.id}', name='{self.agent_name}', tenant_id='{self.tenant_id}', department_id='{self.department_id}')>"


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

    access_level_override = Column(
        String(20),
        nullable=True,
        comment="Agent-specific access level override ('public', 'private', 'both')"
    )

    usage_limits = Column(
        JSONB,
        nullable=True,
        comment="Agent-specific usage limits"
    )

    configured_by = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        comment="User who configured this tool for agent"
    )

    agent = relationship("Agent", back_populates="tool_configs")
    tool = relationship("Tool")
    
    __table_args__ = (
        Index('idx_agent_tool_enabled', 'agent_id', 'is_enabled'),
        Index('idx_agent_tool_override', 'agent_id', 'access_level_override'),
    )
    
    def __repr__(self) -> str:
        return f"<AgentToolConfig(agent_id={self.agent_id}, tool_id={self.tool_id})>"
    

class WorkflowAgent(BaseModel):
    """
    Workflow orchestration agents
    One per tenant for managing multi-agent workflows
    """
    
    __tablename__ = "workflow_agents"

    tenant_id = Column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Tenant ID"
    )
    
    provider_name = Column(
        String(100),
        nullable=False,
        comment="Provider name (e.g. gemini, openai)"
    )
    
    model_name = Column(
        String(100),
        nullable=False,
        comment="Model name (e.g. gemini-pro, gpt-4)"
    )
    
    model_config = Column(
        JSONB,
        nullable=True,
        comment="Model configuration (temperature, max_tokens, etc.)"
    )
    
    max_iterations = Column(
        Integer,
        nullable=False,
        default=10,
        comment="Maximum workflow iterations"
    )
    
    timeout_seconds = Column(
        Integer,
        nullable=False,
        default=300,
        comment="Workflow timeout in seconds"
    )
    
    confidence_threshold = Column(
        Float,
        nullable=False,
        default=0.7,
        comment="Minimum confidence threshold"
    )
    
    is_active = Column(
        Boolean,
        nullable=False,
        default=True,
        server_default=text("TRUE"),
        comment="Whether workflow agent is active"
    )

    # Relationships
    tenant = relationship("Tenant", back_populates="workflow_agent")
    
    __table_args__ = (
        Index('idx_workflow_agent_tenant', 'tenant_id'),
        Index('idx_workflow_agent_active', 'is_active'),
        UniqueConstraint('tenant_id', name='uq_workflow_agent_tenant'),
    )
    
    def get_workflow_config(self) -> Dict[str, Any]:
        """Get workflow configuration"""
        return {
            "id": str(self.id),
            "tenant_id": str(self.tenant_id),
            "provider_name": self.provider_name,
            "model_name": self.model_name,
            "model_config": self.model_config or {},
            "max_iterations": self.max_iterations,
            "timeout_seconds": self.timeout_seconds,
            "confidence_threshold": self.confidence_threshold,
            "is_active": self.is_active
        }
    
    def __repr__(self) -> str:
        return f"<WorkflowAgent(id='{self.id}', tenant_id='{self.tenant_id}', provider='{self.provider_name}')>"
    