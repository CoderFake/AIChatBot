from sqlalchemy import Column, String, Boolean, ForeignKey, Index
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import JSONB, UUID

from models.database.base import BaseModel


class Provider(BaseModel):
    """
    LLM Provider model (OpenAI, Anthropic, Google, etc.)
    Global provider definitions
    """
    
    __tablename__ = "providers"
    
    provider_name = Column(
        String(100),
        nullable=False,
        comment="Provider display name"
    )
    
    is_enabled = Column(
        Boolean,
        nullable=False,
        default=True,
        comment="Whether provider is globally enabled"
    )
    
    base_config = Column(
        JSONB,
        nullable=False,
        comment="Base configuration (endpoints, auth methods, etc.)"
    )
    
    # Relationships
    models = relationship(
        "ProviderModel",
        back_populates="provider",
        cascade="all, delete-orphan"
    )
    
    department_configs = relationship(
        "DepartmentProviderConfig",
        back_populates="provider",
        cascade="all, delete-orphan"
    )
    
    __table_args__ = (
        Index('idx_provider_enabled', 'is_enabled'),
    )
    
    def __repr__(self) -> str:
        return f"<Provider(id='{self.id}', name='{self.provider_name}')>"


class ProviderModel(BaseModel):
    """
    Models provided by each provider
    """
    
    __tablename__ = "provider_models"
    
    provider_id = Column(
        UUID(as_uuid=True),
        ForeignKey("providers.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Provider ID"
    )
    
    model_name = Column(
        String(200),
        nullable=False,
        comment="Model display name"
    )
    
    model_type = Column(
        String(50),
        nullable=False,
        index=True,
        comment="Model type: text, chat, embedding"
    )
    
    is_enabled = Column(
        Boolean,
        nullable=False,
        default=True,
        comment="Whether model is enabled"
    )
    
    model_config = Column(
        JSONB,
        nullable=True,
        comment="Model-specific configuration"
    )
    
    provider = relationship("Provider", back_populates="models")
    
    __table_args__ = (
        Index('idx_provider_model_enabled', 'provider_id', 'is_enabled'),
    )
    
    def __repr__(self) -> str:
        return f"<ProviderModel(id='{self.id}', provider_id={self.provider_id}, model_name='{self.model_name}')>"


class DepartmentProviderConfig(BaseModel):
    """
    Department-level provider configuration with API keys
    Each department can configure different providers
    """
    
    __tablename__ = "department_provider_configs"
    
    department_id = Column(
        UUID(as_uuid=True),
        ForeignKey("departments.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Department ID"
    )
    
    provider_id = Column(
        UUID(as_uuid=True),
        ForeignKey("providers.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Provider ID"
    )
    
    api_key = Column(
        String(500),
        nullable=False,
        comment="Encrypted API key for this provider"
    )
    
    is_enabled = Column(
        Boolean,
        nullable=False,
        default=True,
        comment="Whether this provider config is enabled"
    )
    
    config_data = Column(
        JSONB,
        nullable=True,
        comment="Department-specific provider configuration"
    )
    
    configured_by = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        comment="User who configured this provider"
    )
    
    department = relationship("Department", back_populates="provider_configs")
    provider = relationship("Provider", back_populates="department_configs")
    
    __table_args__ = (
        Index('idx_dept_provider_enabled', 'department_id', 'is_enabled'),
    )
    
    def __repr__(self) -> str:
        return f"<DepartmentProviderConfig(id='{self.id}', dept_id={self.department_id}, provider_id={self.provider_id})>"