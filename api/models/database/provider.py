from sqlalchemy import Column, String, Boolean, JSON, ForeignKey, UniqueConstraint, Index, Integer
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID
from models.database.base import BaseModel


class Provider(BaseModel):
    """
    Provider model để quản lý các nhà cung cấp LLM
    Ví dụ: OpenAI, Anthropic, Google, etc.
    """
    
    __tablename__ = "providers"
    
    name = Column(
        String(100), 
        nullable=False, 
        unique=True, 
        index=True,
        comment="Tên provider (OpenAI, Anthropic, etc.)"
    )
    
    display_name = Column(
        String(200),
        nullable=False,
        comment="Tên hiển thị của provider"
    )
    
    description = Column(
        String(500),
        nullable=True,
        comment="Mô tả về provider"
    )
    
    is_enabled = Column(
        Boolean, 
        nullable=False, 
        default=True,
        comment="Provider có được bật không"
    )
    
    base_config = Column(
        JSON, 
        nullable=False,
        comment="Cấu hình cơ bản của provider (endpoints, auth, etc.)"
    )
    
    # Relationships
    models = relationship(
        "ProviderModel",
        back_populates="provider",
        cascade="all, delete-orphan"
    )
    
    agent_providers = relationship(
        "AgentProvider",
        back_populates="provider",
        cascade="all, delete-orphan"
    )
    
    __table_args__ = (
        Index('idx_provider_enabled', 'is_enabled'),
    )
    
    def __repr__(self) -> str:
        return f"<Provider(name='{self.name}', enabled={self.is_enabled})>"


class ProviderModel(BaseModel):
    """
    Model được cung cấp bởi Provider
    Ví dụ: gpt-4, gpt-3.5-turbo, claude-3-opus, etc.
    """
    
    __tablename__ = "provider_models"
    
    provider_id = Column(
        UUID(as_uuid=True),
        ForeignKey("providers.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="ID của provider"
    )
    
    model_name = Column(
        String(100),
        nullable=False,
        index=True,
        comment="Tên model (gpt-4, claude-3-opus, etc.)"
    )
    
    display_name = Column(
        String(200),
        nullable=False,
        comment="Tên hiển thị của model"
    )
    
    model_type = Column(
        String(50),
        nullable=False,
        index=True,
        comment="Loại model: text, chat, embedding, etc."
    )
    
    max_tokens = Column(
        Integer,
        nullable=True,
        comment="Số token tối đa của model"
    )
    
    is_enabled = Column(
        Boolean,
        nullable=False,
        default=True,
        comment="Model có được bật không"
    )
    
    model_config = Column(
        JSON,
        nullable=True,
        comment="Cấu hình riêng của model"
    )
    
    # Relationships
    provider = relationship("Provider", back_populates="models")
    
    __table_args__ = (
        UniqueConstraint('provider_id', 'model_name', name='uq_provider_model'),
        Index('idx_provider_model_enabled', 'provider_id', 'is_enabled'),
        Index('idx_model_type_enabled', 'model_type', 'is_enabled'),
    )
    
    def __repr__(self) -> str:
        return f"<ProviderModel(provider_id={self.provider_id}, model_name='{self.model_name}')>"


class AgentProvider(BaseModel):
    """
    AgentProvider model để quản lý provider được sử dụng bởi agent
    Mỗi agent có thể có 1 provider để thực hiện LLM calls
    """
    
    __tablename__ = "agent_providers"
    
    agent_id = Column(
        String(100),
        nullable=False,
        index=True,
        comment="ID của agent"
    )
    
    provider_id = Column(
        UUID(as_uuid=True),
        ForeignKey("providers.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="ID của provider được sử dụng"
    )
    
    model_id = Column(
        UUID(as_uuid=True),
        ForeignKey("provider_models.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="ID của model được sử dụng"
    )
    
    is_active = Column(
        Boolean,
        nullable=False,
        default=True,
        comment="AgentProvider có được bật không"
    )
    
    priority = Column(
        Integer,
        nullable=False,
        default=1,
        comment="Độ ưu tiên khi có nhiều provider"
    )
    
    custom_config = Column(
        JSON,
        nullable=True,
        comment="Cấu hình tùy chỉnh cho agent này"
    )
    
    # Relationships  
    provider = relationship("Provider", back_populates="agent_providers")
    model = relationship("ProviderModel")
    
    agent_tools = relationship(
        "AgentTool",
        back_populates="agent_provider",
        cascade="all, delete-orphan"
    )
    
    __table_args__ = (
        UniqueConstraint('agent_id', 'provider_id', name='uq_agent_provider'),
        Index('idx_agent_provider_active', 'agent_id', 'is_active'),
        Index('idx_agent_priority', 'agent_id', 'priority'),
    )
    
    def __repr__(self) -> str:
        return f"<AgentProvider(agent_id='{self.agent_id}', provider_id={self.provider_id}, active={self.is_active})>"


class AgentTool(BaseModel):
    """
    AgentTool model để quản lý tools được sử dụng bởi agent
    Mỗi agent có thể có nhiều tools và có thể bật/tắt từng tool
    """

    __tablename__ = "agent_tools"

    agent_provider_id = Column(
        UUID(as_uuid=True),
        ForeignKey("agent_providers.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="ID của agent provider"
    )
    
    tool_id = Column(
        UUID(as_uuid=True),
        ForeignKey("tools.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="ID của tool"
    )
    
    is_enabled = Column(
        Boolean,
        nullable=False,
        default=True,
        comment="Tool có được bật cho agent này không"
    )
    
    tool_config = Column(
        JSON,
        nullable=True,
        comment="Cấu hình riêng của tool cho agent này"
    )
    
    usage_stats = Column(
        JSON,
        nullable=True,
        comment="Thống kê sử dụng tool: calls_count, success_rate, etc."
    )

    # Relationships
    agent_provider = relationship("AgentProvider", back_populates="agent_tools")
    tool = relationship("Tool")

    __table_args__ = (
        UniqueConstraint('agent_provider_id', 'tool_id', name='uq_agent_tool'),
        Index('idx_agent_tool_enabled', 'agent_provider_id', 'is_enabled'),
        Index('idx_agent_tool_priority', 'agent_provider_id', 'priority'),
    )
    
    def toggle_enabled(self):
        """Bật/tắt tool"""
        self.is_enabled = not self.is_enabled
    
    def increment_usage(self):
        """Tăng counter sử dụng tool"""
        if not self.usage_stats:
            self.usage_stats = {"calls_count": 0, "success_count": 0}
        
        self.usage_stats["calls_count"] = self.usage_stats.get("calls_count", 0) + 1
    
    def increment_success(self):
        """Tăng counter thành công"""
        if not self.usage_stats:
            self.usage_stats = {"calls_count": 0, "success_count": 0}
        
        self.usage_stats["success_count"] = self.usage_stats.get("success_count", 0) + 1
    
    @property
    def success_rate(self) -> float:
        """Tính tỷ lệ thành công"""
        if not self.usage_stats or self.usage_stats.get("calls_count", 0) == 0:
            return 0.0
        
        success_count = self.usage_stats.get("success_count", 0)
        calls_count = self.usage_stats.get("calls_count", 0)
        
        return (success_count / calls_count) * 100

    def __repr__(self) -> str:
        return f"<AgentTool(agent_provider_id={self.agent_provider_id}, tool_id={self.tool_id}, enabled={self.is_enabled})>"

