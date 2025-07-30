from typing import List, Dict, Any, Optional
from sqlalchemy import Column, String, Boolean, Text, Index, Integer, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.sql import text

from models.database.base import BaseModel


class Tenant(BaseModel):
    """
    Tenant model for multi-tenancy
    Each tenant has multiple departments and users
    """
    
    __tablename__ = "tenants"
    
    tenant_name = Column(
        String(200),
        nullable=False,
        comment="Tenant display name"
    )
    
    description = Column(
        Text,
        nullable=True,
        comment="Tenant description"
    )
    
    is_active = Column(
        Boolean,
        nullable=False,
        default=True,
        server_default=text("TRUE"),
        comment="Whether tenant is active"
    )
    
    settings = Column(
        JSONB,
        nullable=True,
        comment="Tenant configuration settings"
    )
    
    departments = relationship(
        "Department",
        back_populates="tenant",
        cascade="all, delete-orphan"
    )
    
    users = relationship(
        "User",
        back_populates="tenant",
        cascade="all, delete-orphan"
    )
    
    __table_args__ = (
        Index('idx_tenant_active', 'is_active'),
    )
    
    def __repr__(self) -> str:
        return f"<Tenant(id='{self.id}', name='{self.tenant_name}')>"


class Department(BaseModel):
    """
    Department model for managing departments within tenant
    """
    
    __tablename__ = "departments"
    
    tenant_id = Column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Tenant ID"
    )
    
    department_name = Column(
        String(200),
        nullable=False,
        comment="Department name"
    )
    
    description = Column(
        Text,
        nullable=True,
        comment="Department description"
    )
    
    is_active = Column(
        Boolean,
        nullable=False,
        default=True,
        server_default=text("TRUE"),
        comment="Whether department is active"
    )
    
    # Relationships
    tenant = relationship("Tenant", back_populates="departments")
    users = relationship("User", back_populates="department")
    
    tool_configs = relationship(
        "DepartmentToolConfig",
        back_populates="department",
        cascade="all, delete-orphan"
    )
    
    provider_configs = relationship(
        "DepartmentProviderConfig",
        back_populates="department",
        cascade="all, delete-orphan"
    )
    
    document_collections = relationship(
        "DocumentCollection",
        back_populates="department",
        cascade="all, delete-orphan"
    )
    
    agent = relationship(
        "Agent",
        back_populates="department",
        uselist=False,
        cascade="all, delete-orphan"
    )
    
    __table_args__ = (
        Index('idx_department_active', 'tenant_id', 'is_active'),
    )
    
    def __repr__(self) -> str:
        return f"<Department(id='{self.id}', name='{self.department_name}')>"