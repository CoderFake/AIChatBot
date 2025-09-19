from sqlalchemy import Column, String, Boolean, ForeignKey, Index, Integer
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import JSONB, UUID
from typing import List, Optional, Dict, Any

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
    
    tenant_configs = relationship(
        "TenantProviderConfig",
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
        default=False,
        comment="Only enabled one model will be used for processing"
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


class TenantProviderConfig(BaseModel):
    """
    Tenant-level provider configuration (API keys rotation, config)
    """
    
    __tablename__ = "tenant_provider_configs"
    
    tenant_id = Column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Tenant ID"
    )
    
    provider_id = Column(
        UUID(as_uuid=True),
        ForeignKey("providers.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Provider ID"
    )
    
    api_keys = Column(
        JSONB,
        nullable=False,
        comment="Array of encrypted API keys for rotation"
    )
    
    current_key_index = Column(
        Integer,
        nullable=False,
        default=0,
        comment="Current active API key index for rotation"
    )
    
    rotation_strategy = Column(
        String(50),
        nullable=False,
        default="round_robin",
        comment="Key rotation strategy: round_robin, random, fallback"
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
        comment="Tenant-specific provider configuration"
    )
    
    configured_by = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        comment="User who configured this provider"
    )
    
    # Relationships
    tenant = relationship("Tenant", back_populates="provider_configs")
    provider = relationship("Provider", back_populates="tenant_configs")
    
    __table_args__ = (
        Index('idx_tenant_provider_enabled', 'tenant_id', 'is_enabled'),
        Index('idx_tenant_provider_rotation', 'provider_id', 'current_key_index'),
    )
    
    def get_api_keys(self) -> List[str]:
        """Get API keys (stored in plain text)"""
        return self.api_keys or []
    
    def get_current_api_key(self) -> Optional[str]:
        """Get current API key"""
        keys = self.get_api_keys()
        if not keys:
            return None
        if self.current_key_index >= len(keys):
            self.current_key_index = 0
        return keys[self.current_key_index]
    
    def rotate_to_next_key(self) -> str:
        """Rotate to next API key and return it"""
        keys = self.get_api_keys()
        if not keys:
            raise ValueError("No API keys available for rotation")
        if self.rotation_strategy == "round_robin":
            self.current_key_index = (self.current_key_index + 1) % len(keys)
        elif self.rotation_strategy == "random":
            import random
            self.current_key_index = random.randint(0, len(keys) - 1)
        elif self.rotation_strategy == "fallback":
            if self.current_key_index < len(keys) - 1:
                self.current_key_index += 1
            else:
                self.current_key_index = 0
        return keys[self.current_key_index]
    
    def add_api_key(self, new_key: str) -> None:
        """Add new API key (stored in plain text)"""
        current_keys = self.api_keys or []

        if new_key not in current_keys:
            current_keys.append(new_key)
            self.api_keys = current_keys
    
    def remove_api_key(self, key_to_remove: str) -> bool:
        """Remove API key by value"""
        current_keys = self.api_keys or []

        if key_to_remove in current_keys:
            remove_index = current_keys.index(key_to_remove)
            current_keys.remove(key_to_remove)

            self.api_keys = current_keys

            if self.current_key_index >= len(current_keys) and current_keys:
                self.current_key_index = 0
            elif self.current_key_index > remove_index:
                self.current_key_index -= 1
            return True
        return False
    
    def set_api_keys(self, keys: List[str]) -> None:
        """Set API keys (stored in plain text)"""
        self.api_keys = keys
        self.current_key_index = 0
    
    def get_cache_data(self) -> Dict[str, Any]:
        """Get data for caching (without plaintext API key)"""
        return {
            "tenant_id": str(self.tenant_id),
            "provider_id": str(self.provider_id),
            "is_enabled": self.is_enabled,
            "rotation_strategy": self.rotation_strategy,
            "config_data": self.config_data or {},
            "key_count": len(self.api_keys or []),
            "current_key_index": self.current_key_index,
            "last_updated": self.updated_at.isoformat() if self.updated_at else None
        }
    
