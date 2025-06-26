from typing import List, Optional, Dict, Any
from sqlalchemy import Column, String, Boolean, Integer, Float, Text, Index, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import JSONB

from models.database.base import BaseModel
from models.database.types import check_document_access
from utils.datetime_utils import CustomDateTime

class Document(BaseModel):
    """
    Document model lưu metadata của tài liệu
    Hỗ trợ phân quyền private/public theo department
    """
    
    __tablename__ = "documents"
    
    # Basic info
    filename = Column(
        String(500),
        nullable=False,
        comment="Tên file gốc"
    )
    
    title = Column(
        String(500),
        nullable=False,
        index=True,
        comment="Tiêu đề tài liệu"
    )
    
    description = Column(
        Text,
        nullable=True,
        comment="Mô tả tài liệu"
    )
    
    # Ownership & Access
    department = Column(
        String(100),
        nullable=False,
        index=True,
        comment="Department sở hữu tài liệu"
    )
    
    access_level = Column(
        String(50),
        nullable=False,
        default="public",
        index=True,
        comment="public, private, internal, confidential, restricted"
    )
    
    uploaded_by = Column(
        String(36),
        ForeignKey("users.id"),
        nullable=False,
        index=True,
        comment="User upload tài liệu"
    )
    
    # File info
    file_size = Column(
        Integer,
        nullable=False,
        comment="Kích thước file (bytes)"
    )
    
    file_type = Column(
        String(20),
        nullable=False,
        index=True,
        comment="Loại file: pdf, docx, txt, md"
    )
    
    content_hash = Column(
        String(64),
        nullable=False,
        index=True,
        comment="SHA-256 hash để detect duplicate"
    )
    
    language = Column(
        String(10),
        nullable=False,
        default="vi",
        index=True,
        comment="Ngôn ngữ: vi, en, ja, ko"
    )
    
    # Processing info
    processing_status = Column(
        String(50),
        nullable=False,
        default="pending",
        index=True,
        comment="pending, processing, completed, failed"
    )
    
    chunk_count = Column(
        Integer,
        nullable=False,
        default=0,
        comment="Số lượng chunks được tạo"
    )
    
    vector_collection = Column(
        String(100),
        nullable=True,
        index=True,
        comment="Collection trong Milvus"
    )
    
    # Storage paths
    storage_path = Column(
        String(1000),
        nullable=True,
        comment="Path trong MinIO"
    )
    
    error_message = Column(
        Text,
        nullable=True,
        comment="Lỗi processing nếu có"
    )
    
    # Stats
    access_count = Column(
        Integer,
        nullable=False,
        default=0,
        comment="Số lần được truy cập"
    )
    
    last_accessed = Column(
        nullable=True,
        comment="Lần truy cập cuối"
    )
    
    # Metadata & references
    tags = Column(
        JSONB,
        nullable=True,
        comment="Tags cho search"
    )
    
    references = Column(
        JSONB,
        nullable=True,
        comment="Thông tin tham khảo: source, url, author, date"
    )
    
    # Relationships
    uploader = relationship("User", foreign_keys=[uploaded_by])
    
    __table_args__ = (
        Index('idx_doc_dept_access', 'department', 'access_level'),
        Index('idx_doc_status', 'processing_status'),
        Index('idx_doc_type_lang', 'file_type', 'language'),
        Index('idx_doc_hash', 'content_hash'),
        Index('idx_doc_collection', 'vector_collection'),
    )
    
    def is_accessible_by_user(self, user_department: str, user_role: str) -> bool:
        """Check xem user có thể access document không"""
        return check_document_access(
            access_level=self.access_level,
            user_role=user_role,
            user_department=user_department,
            document_department=self.department
        )
    
    def record_access(self):
        """Ghi nhận lần truy cập"""
        self.last_accessed = CustomDateTime.now()
        self.access_count += 1
    
    def update_processing(self, status: str, chunk_count: int = None, error: str = None):
        """Cập nhật trạng thái processing"""
        self.processing_status = status
        if chunk_count is not None:
            self.chunk_count = chunk_count
        if error:
            self.error_message = error
    
    def get_reference_info(self) -> Dict[str, Any]:
        """Lấy thông tin reference để citation"""
        if not self.references:
            return {
                "title": self.title,
                "source": "Internal Document",
                "department": self.department,
                "date": self.created_at.strftime("%Y-%m-%d") if self.created_at else None
            }
        
        return self.references
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        data = super().to_dict()
        data.update({
            'file_size_mb': round(self.file_size / (1024 * 1024), 2),
            'is_completed': self.processing_status == "completed",
            'reference_info': self.get_reference_info()
        })
        return data
    
    def __repr__(self) -> str:
        return f"<Document(id={self.id}, title='{self.title}', dept='{self.department}')>"

class DocumentAccessLog(BaseModel):
    """
    Simple access log cho documents
    """
    
    __tablename__ = "document_access_logs"
    
    document_id = Column(
        String(36),
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    
    user_id = Column(
        String(36),
        ForeignKey("users.id"),
        nullable=False,
        index=True
    )
    
    access_type = Column(
        String(50),
        nullable=False,
        comment="VIEW, SEARCH, DOWNLOAD"
    )
    
    query_used = Column(
        Text,
        nullable=True,
        comment="Query search nếu có"
    )
    
    ip_address = Column(
        String(45),
        nullable=True
    )
    
    # Relationships
    document = relationship("Document")
    user = relationship("User")
    
    __table_args__ = (
        Index('idx_access_doc_time', 'document_id', 'created_at'),
        Index('idx_access_user_time', 'user_id', 'created_at'),
    )
    
    def __repr__(self) -> str:
        return f"<DocumentAccessLog(doc={self.document_id}, user={self.user_id}, type='{self.access_type}')>"