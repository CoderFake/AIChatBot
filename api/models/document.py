from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field

from common.types import AccessLevel

class DocumentMetadata(BaseModel):
    """Metadata cho document - Base level từ API"""
    title: Optional[str] = Field(None, description="Tiêu đề tài liệu")
    author: Optional[str] = Field(None, description="Tác giả")
    department: Optional[str] = Field(None, description="Phòng ban liên quan")
    description: Optional[str] = Field(None, description="Mô tả tài liệu")
    language: Optional[str] = Field("vi", description="Ngôn ngữ của tài liệu")

class EnhancedDocumentMetadata(DocumentMetadata):
    """Enhanced metadata với thông tin processing""" 
    filename: Optional[str] = None
    file_size: Optional[int] = None
    file_hash: Optional[str] = None
    file_type: Optional[str] = None
    
    # Processing information
    extraction_method: Optional[str] = "docling"
    export_type: Optional[str] = "doc_chunks"
    processing_timestamp: Optional[str] = None
    total_chunks: Optional[int] = None
    text_length: Optional[int] = None
    
    # Access control
    access_level: AccessLevel = AccessLevel.PUBLIC
    
    # Search optimization
    keywords: Optional[str] = None
    
    def to_milvus_metadata(self) -> Dict[str, Any]:
        """Convert to format phù hợp cho Milvus"""
        return {
            "title": self.title or self.filename or "",
            "author": self.author or "",
            "department": self.department or "",
            "access_level": self.access_level.value,
            "file_type": self.file_type or "unknown",
            "file_size": self.file_size or 0,
            "language": self.language or "vi",
            "keywords": self.keywords or "",
            "extraction_method": self.extraction_method or "docling",
            "export_type": self.export_type or "doc_chunks"
        }
    
    def to_minio_metadata(self) -> Dict[str, Any]:
        """Convert to format phù hợp cho MinIO"""
        return {
            "document-id": "",  # Will be filled by caller
            "department": self.department or "",
            "original-filename": self.filename or "",
            "file-type": self.file_type or "unknown",
            "content-hash": self.file_hash or "",
            "content-size": str(self.file_size or 0),
            "access-level": self.access_level.value,
            "extraction-method": self.extraction_method or "docling"
        }
    
    @classmethod
    def from_api_metadata(
        cls, 
        api_metadata: DocumentMetadata,
        filename: str,
        file_content: bytes,
        **kwargs
    ) -> "EnhancedDocumentMetadata":
        """Create enhanced metadata từ API metadata"""
        import hashlib
        from utils.file_utils import docling_processor
        
        file_hash = hashlib.sha256(file_content).hexdigest()
        file_type = docling_processor.get_file_type(filename)
        
        return cls(
            # Copy từ API metadata
            title=api_metadata.title,
            author=api_metadata.author,
            department=api_metadata.department,
            description=api_metadata.description,
            language=api_metadata.language,
            
            # Add file information
            filename=filename,
            file_size=len(file_content),
            file_hash=file_hash,
            file_type=file_type.value,
            
            # Add processing defaults
            **kwargs
        )

class MetadataTransformer:
    """Utility class để transform metadata giữa các layers"""
    
    @staticmethod
    def api_to_enhanced(
        api_metadata: DocumentMetadata,
        filename: str,
        file_content: bytes,
        **processing_data
    ) -> EnhancedDocumentMetadata:
        """Transform API metadata thành enhanced metadata"""
        return EnhancedDocumentMetadata.from_api_metadata(
            api_metadata, filename, file_content, **processing_data
        )
    
    @staticmethod
    def enhanced_to_milvus_entities(
        enhanced_metadata: EnhancedDocumentMetadata,
        document_id: str,
        chunk_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Transform enhanced metadata thành Milvus entities format"""
        milvus_metadata = enhanced_metadata.to_milvus_metadata()
        
        # Add document và chunk specific data
        milvus_metadata.update({
            "document_id": document_id,
            "chunk_index": chunk_data.get("chunk_index", 0),
            "content": chunk_data.get("content", ""),
            "created_at": int(chunk_data.get("created_at", 0)),
            "updated_at": int(chunk_data.get("updated_at", 0)),
            "bm25_score": chunk_data.get("bm25_score", 0.0)
        })
        
        return milvus_metadata
    
    @staticmethod
    def validate_metadata_consistency(metadata: EnhancedDocumentMetadata) -> List[str]:
        """Validate metadata consistency và return list of issues"""
        issues = []
        
        if not metadata.filename:
            issues.append("Missing filename")
        
        if not metadata.file_size or metadata.file_size <= 0:
            issues.append("Invalid file_size")
        
        if not metadata.file_hash:
            issues.append("Missing file_hash")
        
        if metadata.department and metadata.department not in ["HR", "IT", "FINANCE", "GENERAL"]:
            issues.append(f"Invalid department: {metadata.department}")
        
        return issues

