from sqlalchemy import Column, String, Boolean, Text, Index
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import JSONB
from models.database.base import BaseModel


class Provider(BaseModel):
    """
    Provider model
    """
    
    __tablename__ = "providers"
    
    name = Column(
        String(100), 
        nullable=False, 
        unique=True, 
        index=True,
        comment="Tên provider: gemini, ollama, mistral, etc."
    )
    
    display_name = Column(
        String(200),
        nullable=False,
        comment="Tên hiển thị"
    )
    
    description = Column(
        Text,
        nullable=True,
        comment="Mô tả provider"
    )
    
    is_enabled = Column(
        Boolean, 
        nullable=False, 
        default=False, 
        index=True,
        comment="Provider có được bật không"
    )
    
    provider_config = Column(
        JSONB, 
        nullable=True,
        comment="Config: {api_url: '', timeout: 60}"
    )
    
    models = Column(
        JSONB,
        nullable=True,
        comment="Danh sách models: ['gemini-2.0-flash', 'gemini-1.5-pro']"
    )
    
    default_model = Column(
        String(100),
        nullable=True,
        comment="Model mặc định"
    )
    
    __table_args__ = (
        Index('idx_provider_enabled', 'is_enabled'),
    )
    
    def get_models_list(self):
        """Lấy list models"""
        return self.models or []
    
    def __repr__(self) -> str:
        return f"<Provider(name='{self.name}', enabled={self.is_enabled})>"


