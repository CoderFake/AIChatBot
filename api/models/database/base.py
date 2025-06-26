from typing import Any, Dict
from sqlalchemy import Column, String, DateTime, Boolean, text
from sqlalchemy.ext.declarative import declared_attr
from sqlalchemy.orm import declarative_base
from sqlalchemy.dialects.postgresql import UUID
from utils.datetime_utils import CustomDateTime as datetime


Base = declarative_base()


class TimestampMixin:
    """
    Mixin để thêm timestamp fields cho tất cả models
    """
    
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.now,
        server_default=text("CURRENT_TIMESTAMP")
    )
    
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.now,
        onupdate=datetime.now,
        server_default=text("CURRENT_TIMESTAMP")
    )


class SoftDeleteMixin:
    """
    Mixin để thêm soft delete functionality
    """
    
    is_deleted = Column(Boolean, nullable=False, default=False, server_default=text("FALSE"))
    deleted_at = Column(DateTime(timezone=True), nullable=True)
    deleted_by = Column(String(36), nullable=True)
    
    def soft_delete(self, user_id: str = None):
        """
        Soft delete record
        """
        self.is_deleted = True
        self.deleted_at = datetime.now()
        if user_id:
            self.deleted_by = user_id
    
    def restore(self):
        """
        Restore soft deleted record
        """
        self.is_deleted = False
        self.deleted_at = None
        self.deleted_by = None


class AuditMixin:
    """
    Mixin để thêm audit trail fields
    """
    
    created_by = Column(String(36), nullable=True, comment="User ID của người tạo record")
    updated_by = Column(String(36), nullable=True, comment="User ID của người update record cuối")
    
    version = Column(
        String(50), 
        nullable=False, 
        default="1.0.0",
        comment="Version của record để tracking changes"
    )
    
    metadata_ = Column(
        "metadata",
        String,
        nullable=True,
        comment="Additional metadata dưới dạng JSON string"
    )


class BaseModel(Base, TimestampMixin, SoftDeleteMixin, AuditMixin):
    """
    Base model class cho tất cả database models
    Kết hợp tất cả mixins cần thiết
    """
    
    __abstract__ = True
    
    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
        comment="Primary key UUID"
    )
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Chuyển model instance thành dictionary
        """
        result = {}
        for column in self.__table__.columns:
            value = getattr(self, column.name)
            if isinstance(value, datetime):
                result[column.name] = value.isoformat()
            else:
                result[column.name] = value
        return result
    
    def update_from_dict(self, data: Dict[str, Any], user_id: str = None):
        """
        Update model từ dictionary data
        """
        for key, value in data.items():
            if hasattr(self, key) and key not in ['id', 'created_at']:
                setattr(self, key, value)
        
        if user_id:
            self.updated_by = user_id
        
        self.updated_at = datetime.now()
    
    @classmethod
    def get_table_name(cls) -> str:
        """
        Lấy table name của model
        """
        return cls.__tablename__
    
    @classmethod
    def get_primary_key_column(cls) -> str:
        """
        Lấy primary key column name
        """
        return "id"
    
    def __repr__(self) -> str:
        """
        String representation của model
        """
        return f"<{self.__class__.__name__}(id={self.id})>"


class BaseNamedModel(BaseModel):
    """
    Base model với name và description fields
    Dành cho các models cần có tên và mô tả
    """
    
    __abstract__ = True
    
    name = Column(
        String(255),
        nullable=False,
        index=True,
        comment="Tên của entity"
    )
    
    description = Column(
        String,
        nullable=True,
        comment="Mô tả chi tiết của entity"
    )
    
    is_active = Column(
        Boolean,
        nullable=False,
        default=True,
        server_default=text("TRUE"),
        comment="Trạng thái active của entity"
    )
    
    def activate(self):
        """
        Activate entity
        """
        self.is_active = True
    
    def deactivate(self):
        """
        Deactivate entity
        """
        self.is_active = False
    
    def __repr__(self) -> str:
        return f"<{self.__class__.__name__}(id={self.id}, name='{self.name}')>"


class BaseConfigModel(BaseNamedModel):
    """
    Base model cho configuration entities
    """
    
    __abstract__ = True
    
    config_type = Column(
        String(100),
        nullable=False,
        index=True,
        comment="Loại configuration"
    )
    
    config_data = Column(
        String,
        nullable=True,
        comment="Configuration data dưới dạng JSON string"
    )
    
    is_default = Column(
        Boolean,
        nullable=False,
        default=False,
        server_default=text("FALSE"),
        comment="Có phải configuration mặc định không"
    )
    
    priority = Column(
        String(20),
        nullable=False,
        default="normal",
        comment="Mức độ ưu tiên: low, normal, high, critical"
    )


class DatabaseModel:
    """
    Utility class để quản lý database models
    """
    
    @staticmethod
    def get_all_table_names() -> list:
        """
        Lấy tất cả table names trong database
        """
        return [table.name for table in Base.metadata.tables.values()]
    
    @staticmethod
    def get_model_by_tablename(table_name: str):
        """
        Lấy model class theo table name
        """
        for mapper in Base.registry.mappers:
            model = mapper.class_
            if hasattr(model, '__tablename__') and model.__tablename__ == table_name:
                return model
        return None
    
    @staticmethod
    def create_all_indexes():
        """
        Tạo tất cả indexes cho performance optimization
        """
        from sqlalchemy import Index
        
        indexes = [
            Index('idx_created_at', 'created_at'),
            Index('idx_updated_at', 'updated_at'),
            Index('idx_is_active', 'is_active'),
            Index('idx_is_deleted', 'is_deleted'),
        ]
        
        return indexes
    
    @staticmethod
    def get_audit_info(model_instance) -> Dict[str, Any]:
        """
        Lấy audit information từ model instance
        """
        if not isinstance(model_instance, BaseModel):
            return {}
        
        return {
            "id": str(model_instance.id),
            "table_name": model_instance.__tablename__,
            "created_at": model_instance.created_at.isoformat() if model_instance.created_at else None,
            "updated_at": model_instance.updated_at.isoformat() if model_instance.updated_at else None,
            "created_by": model_instance.created_by,
            "updated_by": model_instance.updated_by,
            "version": model_instance.version,
            "is_deleted": model_instance.is_deleted
        }