from typing import List, Dict, Any, Optional
from sqlalchemy import Column, String, Boolean, Text, Index, Integer, ForeignKey, UniqueConstraint
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
    
    sub_domain = Column(
        String(255),
        nullable=True,
        unique=True,
        index=True,
        comment="Subdomain for tenant"
    )
    
    description = Column(
        Text,
        nullable=True,
        comment="Tenant description"
    )
    
    timezone = Column(
        String(50),
        nullable=False,
        default="UTC",
        server_default=text("'UTC'"),
        comment="Tenant timezone (e.g. Asia/Ho_Chi_Minh)"
    )
    
    locale = Column(
        String(10),
        nullable=False,
        default="en_US",
        server_default=text("'en_US'"),
        comment="Tenant locale (e.g. vi_VN, en_US)"
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
    
    # Relationships
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

    provider_configs = relationship(
        "TenantProviderConfig",
        back_populates="tenant",
        cascade="all, delete-orphan"
    )

    tool_configs = relationship(
        "TenantToolConfig",
        back_populates="tenant",
        cascade="all, delete-orphan"
    )
    
    workflow_agent = relationship(
        "WorkflowAgent",
        back_populates="tenant",
        uselist=False,
        cascade="all, delete-orphan"
    )

    chat_sessions = relationship(
        "ChatSession",
        back_populates="tenant"
    )
    
    __table_args__ = (
        Index('idx_tenant_active', 'is_active'),
        Index('idx_tenant_timezone', 'timezone'),
        Index('idx_tenant_subdomain', 'sub_domain'),
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
        UniqueConstraint('tenant_id', 'department_name', name='uq_department_tenant_name'),
    )
    
    def __repr__(self) -> str:
        return f"<Department(id='{self.id}', name='{self.department_name}')>"