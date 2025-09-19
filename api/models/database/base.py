from typing import Dict, Any, Optional
from sqlalchemy import Column, String, Boolean, DateTime, UUID as SQLAlchemyUUID
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql import text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from utils.datetime_utils import DateTimeManager, CustomDateTime

Base = declarative_base()


class TimestampMixin:
    """
    Mixin for timestamp fields
    Provides created_at and updated_at fields
    Database uses server default, but application can override for tenant operations
    """
    
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
        comment="Record creation timestamp"
    )
    
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
        comment="Record last update timestamp"
    )


class SoftDeleteMixin:
    """
    Mixin for soft delete functionality
    Provides is_deleted field and soft delete methods
    """
    
    is_deleted = Column(
        Boolean,
        nullable=False,
        default=False,
        server_default=text("FALSE"),
        comment="Soft delete flag"
    )
    
    deleted_at = Column(
        DateTime(timezone=True),
        nullable=True,
        comment="Soft delete timestamp"
    )
    
    def soft_delete_maintainer(self):
        """Mark record as deleted using system time (for maintainer operations)"""
        self.is_deleted = True
        self.deleted_at = DateTimeManager._now()
    
    async def soft_delete_tenant(self, tenant_id: Optional[str], db: Optional[AsyncSession] = None):
        """Mark record as deleted using tenant time (for tenant operations)"""
        self.is_deleted = True
        self.deleted_at = await DateTimeManager.tenant_now_cached(tenant_id, db)
    
    def restore(self):
        """Restore soft deleted record"""
        self.is_deleted = False
        self.deleted_at = None


class AuditMixin:
    """
    Mixin for audit trail
    Tracks who created and updated records
    """
    
    created_by = Column(
        UUID(as_uuid=True),
        nullable=True,
        comment="User ID who created this record"
    )
    
    updated_by = Column(
        UUID(as_uuid=True),
        nullable=True,
        comment="User ID who last updated this record"
    )
    
    version = Column(
        String(20),
        nullable=False,
        default="1.0.0",
        comment="Record version for change tracking"
    )
    
    metadata_ = Column(
        "metadata",
        String,
        nullable=True,
        comment="Additional metadata as JSON string"
    )


class BaseModel(Base, TimestampMixin, SoftDeleteMixin, AuditMixin):
    """
    Base model class for all database models
    Provides both maintainer and tenant operation methods
    """
    
    __abstract__ = True
    
    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
        comment="Primary key UUID"
    )
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert model instance to dictionary"""
        result = {}
        for column in self.__table__.columns:
            value = getattr(self, column.name)
            if isinstance(value, (CustomDateTime, DateTimeManager)):
                result[column.name] = value.isoformat()
            else:
                result[column.name] = value
        return result
    
    def update_from_dict_maintainer(self, data: Dict[str, Any], user_id: Optional[str] = None):
        """
        Update model from dictionary data using system time (for maintainer operations).
        Use for: Tool management, Provider management, System maintenance
        """
        for key, value in data.items():
            if hasattr(self, key) and key not in ['id', 'created_at']:
                setattr(self, key, value)
        
        if user_id:
            self.updated_by = user_id
        
        self.updated_at = DateTimeManager._now()
    
    async def update_from_dict_tenant(self, data: Dict[str, Any], user_id: Optional[str], tenant_id: Optional[str], db: Optional[AsyncSession]):
        """
        Update model from dictionary data using tenant time (for tenant operations).
        Use for: User CRUD, Business logic, Tenant-level operations
        """
        for key, value in data.items():
            if hasattr(self, key) and key not in ['id', 'created_at']:
                setattr(self, key, value)
        
        if user_id:
            self.updated_by = user_id
        
        self.updated_at = await DateTimeManager.tenant_now_cached(tenant_id, db)
    
    @classmethod
    def get_table_name(cls) -> str:
        """Get table name of model"""
        return cls.__tablename__
    
    @classmethod
    def get_primary_key_column(cls) -> str:
        """Get primary key column name"""
        return "id"
    
    def __repr__(self) -> str:
        """String representation of model"""
        return f"<{self.__class__.__name__}(id={self.id})>"


class DatabaseModel:
    """
    Utility class for database model management
    """
    
    @staticmethod
    def get_all_table_names() -> list:
        """Get all table names in database"""
        return [table.name for table in Base.metadata.tables.values()]
    
    @staticmethod
    def get_model_by_tablename(table_name: str):
        """Get model class by table name"""
        for mapper in Base.registry.mappers:
            model = mapper.class_
            if hasattr(model, '__tablename__') and model.__tablename__ == table_name:
                return model
        return None
    
    @staticmethod
    def get_audit_info(model_instance) -> Dict[str, Any]:
        """Get audit information from model instance"""
        if not isinstance(model_instance, BaseModel):
            return {}
        
        return {
            "id": str(model_instance.id),
            "table_name": model_instance.__tablename__,
            "created_at": model_instance.created_at.isoformat() if model_instance.created_at else None,
            "updated_at": model_instance.updated_at.isoformat() if model_instance.updated_at else None,
            "created_by": str(model_instance.created_by) if model_instance.created_by else None,
            "updated_by": str(model_instance.updated_by) if model_instance.updated_by else None,
            "version": model_instance.version,
            "is_deleted": model_instance.is_deleted
        }