"""
Document models with hierarchical folder structure and access control
Supports private/public collections for Milvus
"""
from sqlalchemy import Column, String, Boolean, Integer, Text, ForeignKey, UniqueConstraint, Index
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import JSONB, UUID
from models.database.types import RoleTypes, DocumentAccessLevel, DBDocumentPermissionLevel

from models.database.base import BaseModel


class DocumentFolder(BaseModel):
    """
    Hierarchical folder structure for documents
    Recursive folder organization within departments
    """
    
    __tablename__ = "document_folders"
    
    department_id = Column(
        UUID(as_uuid=True),
        ForeignKey("departments.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Department ID"
    )
    
    folder_name = Column(
        String(255),
        nullable=False,
        comment="Folder name"
    )
    
    folder_path = Column(
        String(1000),
        nullable=False,
        index=True,
        comment="Full folder path"
    )
    
    parent_folder_id = Column(
        UUID(as_uuid=True),
        ForeignKey("document_folders.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
        comment="Parent folder ID for recursive structure"
    )
    
    access_level = Column(
        String(20),
        nullable=False,
        default="public",
        index=True,
        comment="Access level: private, public"
    )
    
    created_by = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        comment="User who created this folder"
    )
    
    # Relationships
    department = relationship("Department")
    parent_folder = relationship("DocumentFolder", remote_side="DocumentFolder.id")
    documents = relationship("Document", back_populates="folder")
    
    __table_args__ = (
        UniqueConstraint('department_id', 'folder_path', name='uq_dept_folder_path'),
        Index('idx_folder_access', 'department_id', 'access_level'),
    )
    
    def __repr__(self) -> str:
        return f"<DocumentFolder(path='{self.folder_path}', access='{self.access_level}')>"


class DocumentCollection(BaseModel):
    """
    Milvus collections for vector storage
    Separate private and public collections per department
    """
    
    __tablename__ = "document_collections"
    
    department_id = Column(
        UUID(as_uuid=True),
        ForeignKey("departments.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Department ID"
    )
    
    collection_name = Column(
        String(100),
        nullable=False,
        unique=True,
        index=True,
        comment="Milvus collection name"
    )
    
    collection_type = Column(
        String(20),
        nullable=False,
        index=True,
        comment="Collection type: private_milvus, public_milvus"
    )
    
    is_active = Column(
        Boolean,
        nullable=False,
        default=True,
        comment="Whether collection is active"
    )
    
    vector_config = Column(
        JSONB,
        nullable=True,
        comment="Vector configuration settings"
    )
    
    document_count = Column(
        Integer,
        nullable=False,
        default=0,
        comment="Number of documents in collection"
    )
    
    # Relationships
    department = relationship("Department", back_populates="document_collections")
    documents = relationship("Document", back_populates="collection")
    
    __table_args__ = (
        UniqueConstraint('department_id', 'collection_type', name='uq_dept_collection_type'),
        Index('idx_collection_active', 'is_active'),
    )
    
    def __repr__(self) -> str:
        return f"<DocumentCollection(name='{self.collection_name}', type='{self.collection_type}')>"


class Document(BaseModel):
    """
    Document metadata with folder structure and access control
    Links to Milvus collections for vector storage
    """
    
    __tablename__ = "documents"
    
    # Basic information
    filename = Column(
        String(500),
        nullable=False,
        comment="Original filename"
    )
    
    title = Column(
        String(500),
        nullable=False,
        index=True,
        comment="Document title"
    )
    
    description = Column(
        Text,
        nullable=True,
        comment="Document description"
    )
    
    # Relationships
    department_id = Column(
        UUID(as_uuid=True),
        ForeignKey("departments.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Department ID"
    )
    
    folder_id = Column(
        UUID(as_uuid=True),
        ForeignKey("document_folders.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="Folder ID for organization"
    )
    
    collection_id = Column(
        UUID(as_uuid=True),
        ForeignKey("document_collections.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="Milvus collection ID"
    )
    
    uploaded_by = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=False,
        index=True,
        comment="User who uploaded document"
    )
    
    # Access control
    access_level = Column(
        String(20),
        nullable=False,
        default="public",
        index=True,
        comment="Access level: private, public"
    )
    
    # File information
    file_size = Column(
        Integer,
        nullable=False,
        comment="File size in bytes"
    )
    
    file_type = Column(
        String(20),
        nullable=False,
        index=True,
        comment="File type: pdf, docx, txt, etc."
    )
    
    storage_key = Column(
        String(1000),
        nullable=False,
        unique=True,
        index=True,
        comment="MinIO/S3 storage key"
    )
    
    bucket_name = Column(
        String(100),
        nullable=False,
        comment="MinIO bucket name"
    )
    
    # Processing status
    processing_status = Column(
        String(20),
        nullable=False,
        default="pending",
        index=True,
        comment="Processing status: pending, processing, completed, failed"
    )
    
    vector_status = Column(
        String(20),
        nullable=False,
        default="pending",
        index=True,
        comment="Vector processing status: pending, processing, completed, failed"
    )
    
    chunk_count = Column(
        Integer,
        nullable=False,
        default=0,
        comment="Number of text chunks"
    )
    
    # Relationships
    department = relationship("Department")
    folder = relationship("DocumentFolder", back_populates="documents")
    collection = relationship("DocumentCollection", back_populates="documents")
    uploaded_by_user = relationship("User", back_populates="documents")
    
    __table_args__ = (
        Index('idx_doc_dept_access', 'department_id', 'access_level'),
        Index('idx_doc_status', 'processing_status', 'vector_status'),
        Index('idx_doc_type', 'file_type'),
        Index('idx_doc_storage', 'bucket_name', 'storage_key'),
    )
    
    def get_storage_path(self) -> str:
        """Get full storage path for MinIO/S3"""
        return f"{self.bucket_name}/{self.storage_key}"
    
    def get_access_type(self) -> str:
        """Get access type for Milvus collection routing"""
        return DBDocumentPermissionLevel.PRIVATE.value if self.access_level == DocumentAccessLevel.PRIVATE.value else DBDocumentPermissionLevel.PUBLIC.value
    
    def can_access(self, user_id: str, user_department_id: str, user_role: str) -> bool:
        """Check if user can access this document"""
        
        if str(self.department_id) != user_department_id:
            if user_role not in [RoleTypes.ADMIN.value, RoleTypes.MAINTAINER.value]:
                return False
        
        if self.access_level == DocumentAccessLevel.PRIVATE.value:
            if str(self.uploaded_by) == user_id:
                return True
            if user_role in [RoleTypes.ADMIN.value, RoleTypes.MAINTAINER.value, RoleTypes.DEPT_ADMIN.value, RoleTypes.DEPT_MANAGER.value]:
                return True
            return False
        
        return True
    
    def __repr__(self) -> str:
        return f"<Document(title='{self.title}', access='{self.access_level}')>"