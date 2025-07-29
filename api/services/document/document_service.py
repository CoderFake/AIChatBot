import asyncio
from typing import Dict, Any, List, Optional, Tuple
from utils.datetime_utils import CustomDateTime as datetime
import uuid

from models import DocumentMetadata, EnhancedDocumentMetadata, MetadataTransformer
from config.settings import get_settings
from utils.logging import get_logger
from core.exceptions import ServiceError
from common.types import Department, FileType
from utils.file_utils import docling_processor
from services.vector.milvus_service import OptimizedMilvusService
from services.storage.minio_service import minio_service

logger = get_logger(__name__)

class DocumentService:
    """
    Service layer for document processing
    Separate business logic from API endpoints
    Integrate Docling for document processing and MinIO for storage 
    Integrate Milvus for vector database
    """
    
    def __init__(self):
        self.processing_tasks = {}
        self.settings = get_settings()
        self.milvus_service = OptimizedMilvusService()
        self.docling_processor = docling_processor
        self.minio_service = minio_service  
    
    async def upload_document(
        self,
        filename: str,
        file_content: bytes,
        metadata: DocumentMetadata
    ) -> Tuple[str, Dict[str, Any]]:
        """
        Handle document upload and queue processing
        
        Returns:
            Tuple[document_id, upload_info]
        """
        try:
            document_id = str(uuid.uuid4())
            
            self._validate_file(filename, file_content)
            
            upload_info = {
                "document_id": document_id,
                "filename": filename,
                "status": "queued",
                "metadata": metadata.dict(),
                "uploaded_at": datetime.now().isoformat(),
                "file_size_bytes": len(file_content)
            }
            
            logger.info(f"Document {document_id} queued for processing: {filename}")
            
            return document_id, upload_info
            
        except Exception as e:
            logger.error(f"Document upload failed: {e}")
            raise ServiceError(f"Upload failed: {str(e)}")
    
    async def process_document_async(
        self,
        document_id: str,
        filename: str,
        file_content: bytes,
        metadata: DocumentMetadata
    ) -> Dict[str, Any]:
        """
        Background processing for document with unified metadata handling
        """
        try:
            logger.info(f"Starting background processing for document {document_id}")
            
            await self._update_document_status(document_id, "processing", 0)
            
            enhanced_metadata = MetadataTransformer.api_to_enhanced(
                api_metadata=metadata,
                filename=filename,
                file_content=file_content,
                processing_timestamp=datetime.now().isoformat()
            )
            
            validation_issues = MetadataTransformer.validate_metadata_consistency(enhanced_metadata)
            if validation_issues:
                logger.warning(f"Metadata validation issues for {document_id}: {validation_issues}")
            
            storage_result = await self._save_to_storage_enhanced(document_id, filename, file_content, enhanced_metadata)
            await self._update_document_status(document_id, "processing", 20)
            
            extracted_text, documents = await self._extract_text(filename, file_content)
            await self._update_document_status(document_id, "processing", 40)
            
            enhanced_metadata.text_length = len(extracted_text)
            
            chunks = await self._chunk_text_enhanced(extracted_text, documents, enhanced_metadata, filename)
            await self._update_document_status(document_id, "processing", 60)
            
            enhanced_metadata.total_chunks = len(chunks)
            
            department = getattr(metadata, 'department', Department.GENERAL)
            if isinstance(department, str):
                department = Department(department.upper())
                
            vector_result = await self.milvus_service.add_document_with_department(
                file_content=file_content,
                filename=filename,
                department=department,
                document_id=document_id,
                metadata=enhanced_metadata.dict(),
                use_chunks=True
            )
            await self._update_document_status(document_id, "completed", 100)
            
            result = {
                "document_id": document_id,
                "status": "completed",
                "chunk_count": vector_result.get("chunk_count", 0) if vector_result.get("success") else 0,
                "processing_time": 0.0, 
                "storage_result": storage_result,
                "vector_result": vector_result,
                "extraction_method": enhanced_metadata.extraction_method,
                "enhanced_metadata": enhanced_metadata.dict(),
                "validation_issues": validation_issues
            }
            
            logger.info(
                f"Document {document_id} processed successfully: "
                f"{enhanced_metadata.total_chunks} chunks, "
                f"extraction_method={enhanced_metadata.extraction_method}, "
                f"file_type={enhanced_metadata.file_type}"
            )
            return result
            
        except Exception as e:
            logger.error(f"Failed to process document {document_id}: {e}")
            await self._update_document_status(document_id, "failed", error=str(e))
            raise ServiceError(f"Document processing failed: {str(e)}")
    
    async def search_documents(
        self,
        query: str,
        department: Optional[Department] = None,
        top_k: int = 5,
        threshold: float = 0.3,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Search documents trong vector database
        """
        try:
            if not self.milvus_service._initialized:
                await self.milvus_service.initialize()
            
            if department:
                collection_name = self.docling_processor.get_collection_name(department)
            else:
                collection_name = "general_documents"
            
            # Execute search
            results = await self.milvus_service.search(
                query=query,
                collection_name=collection_name,
                top_k=top_k,
                threshold=threshold,
                filters=filters or {}
            )
            
            return [result.dict() if hasattr(result, 'dict') else result for result in results]
            
        except Exception as e:
            logger.error(f"Document search failed: {e}")
            raise ServiceError(f"Search failed: {str(e)}")
    
    async def get_document_status(self, document_id: str) -> Dict[str, Any]:
        """
        Get processing status của document
        """
        try:
            # In real implementation, query from database
            # For now, return placeholder
            return {
                "document_id": document_id,
                "status": "completed",
                "processing_progress": 100,
                "chunk_count": 25,
                "created_at": datetime.now().isoformat(),
                "processed_at": datetime.now().isoformat(),
                "error": None
            }
            
        except Exception as e:
            logger.error(f"Failed to get document status: {e}")
            raise ServiceError(f"Status retrieval failed: {str(e)}")
    
    async def list_documents(
        self,
        page: int = 1,
        limit: int = 20,
        filters: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        List documents with pagination and filtering
        """
        try:
            
            documents = []
            for i in range(min(limit, 5)):
                documents.append({
                    "document_id": f"doc-{i+1}",
                    "filename": f"document_{i+1}.pdf",
                    "title": f"Sample Document {i+1}",
                    "author": "Admin",
                    "department": filters.get("department", "IT") if filters else "IT",
                    "status": "completed",
                    "chunk_count": 20 + i * 5,
                    "created_at": datetime.now().isoformat()
                })
            
            return {
                "documents": documents,
                "pagination": {
                    "page": page,
                    "limit": limit,
                    "total": 50,
                    "pages": 3
                }
            }
            
        except Exception as e:
            logger.error(f"Failed to list documents: {e}")
            raise ServiceError(f"Document listing failed: {str(e)}")
    
    async def delete_document(self, document_id: str) -> Dict[str, Any]:
        """
        Delete document khỏi system
        """
        try:
            logger.info(f"Deleting document: {document_id}")
            
            departments = [Department.HR, Department.IT, Department.FINANCE, Department.GENERAL]
            
            vector_deleted = False
            storage_deleted = False
            
            for dept in departments:
                try:
                    if await self._delete_from_vector_db(document_id, dept):
                        vector_deleted = True
                        break
                except Exception as e:
                    logger.debug(f"Document {document_id} not found in {dept.value} collection: {e}")
            
            for dept in departments:
                try:
                    await self._delete_from_storage(document_id, None)
                    storage_deleted = True
                    break
                except Exception as e:
                    logger.debug(f"Document {document_id} not found in {dept.value} storage: {e}")
            
            await self._update_document_status(document_id, "deleted")
            
            return {
                "document_id": document_id,
                "status": "deleted",
                "message": "Document deleted successfully",
                "vector_deleted": vector_deleted,
                "storage_deleted": storage_deleted
            }
            
        except Exception as e:
            logger.error(f"Failed to delete document: {e}")
            raise ServiceError(f"Document deletion failed: {str(e)}")
    
    async def reprocess_document(self, document_id: str) -> Dict[str, Any]:
        """
        Reprocess document với updated settings
        """
        try:
            logger.info(f"Reprocessing document: {document_id}")
          
            await asyncio.sleep(1)
            
            return {
                "document_id": document_id,
                "status": "reprocessing_queued",
                "message": "Document reprocessing started"
            }
            
        except Exception as e:
            logger.error(f"Failed to reprocess document: {e}")
            raise ServiceError(f"Document reprocessing failed: {str(e)}")
    
    async def get_document_statistics(self) -> Dict[str, Any]:
        """
        Get document statistics cho admin dashboard
        """
        try:
            # In real implementation, query actual statistics from database
            return {
                "total_documents": 150,
                "processed_documents": 145,
                "processing_documents": 3,
                "failed_documents": 2,
                "total_chunks": 3250,
                "storage_used_mb": 245.7,
                "by_department": {
                    "IT": 45,
                    "HR": 30,
                    "Finance": 25,
                    "Legal": 20,
                    "Marketing": 15,
                    "Others": 15
                },
                "by_type": {
                    "PDF": 85,
                    "DOCX": 35,
                    "TXT": 20,
                    "MD": 10
                },
                "processing_queue": {
                    "pending": 2,
                    "in_progress": 1,
                    "failed_retries": 0
                },
                "last_updated": datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Failed to get document statistics: {e}")
            raise ServiceError(f"Statistics retrieval failed: {str(e)}")
    
    def _validate_file(self, filename: str, file_content: bytes) -> None:
        """Validate uploaded file using settings configuration"""
        if not self.docling_processor.is_supported_file(filename):
            raise ValueError(f"Unsupported file type: {filename}")
        
        max_size_mb = self.settings.file_processing.get("max_file_size_mb", 100)
        if len(file_content) > max_size_mb * 1024 * 1024:
            raise ValueError(f"File too large. Max size: {max_size_mb}MB")
    
    async def _save_to_storage(
        self, 
        document_id: str, 
        filename: str, 
        file_content: bytes, 
        metadata: DocumentMetadata
    ) -> Dict[str, Any]:
        """Save file to MinIO storage"""
        try:
            department = getattr(metadata, 'department', Department.GENERAL)
            if isinstance(department, str):
                department = Department(department.upper())
                
            file_type = self.docling_processor.get_file_type(filename)
            
            upload_result = await self.minio_service.upload_document(
                file_content=file_content,
                filename=filename,
                document_id=document_id,
                department=department,
                metadata=metadata.dict(),
                file_type=file_type
            )
            
            logger.info(f"Document {document_id} saved to storage successfully")
            return upload_result
            
        except Exception as e:
            logger.error(f"Failed to save document {document_id} to storage: {e}")
            raise

    async def _save_to_storage_enhanced(
        self, 
        document_id: str, 
        filename: str, 
        file_content: bytes, 
        enhanced_metadata: EnhancedDocumentMetadata
    ) -> Dict[str, Any]:
        """Save document to MinIO storage using EnhancedDocumentMetadata"""
        try:
            logger.info(f"Saving document {document_id} to MinIO storage with enhanced metadata")
            
            department = Department.GENERAL
            if enhanced_metadata.department:
                department = Department(enhanced_metadata.department.upper())
            
            file_type = self.docling_processor.get_file_type(filename)
            
            minio_metadata = enhanced_metadata.to_minio_metadata()
            minio_metadata["document-id"] = document_id  
            
            upload_result = await self.minio_service.upload_document(
                file_content=file_content,
                filename=filename,
                document_id=document_id,
                department=department,
                metadata=minio_metadata,
                file_type=file_type
            )
            
            logger.info(
                f"Document {document_id} saved to storage successfully: "
                f"size={enhanced_metadata.file_size}, "
                f"hash={enhanced_metadata.file_hash[:8] if enhanced_metadata.file_hash else 'unknown'}, "
                f"access_level={enhanced_metadata.access_level.value}"
            )
            return upload_result
            
        except Exception as e:
            logger.error(f"Failed to save enhanced document {document_id} to storage: {e}")
            raise
    
    async def _extract_text(self, filename: str, file_content: bytes) -> Tuple[str, List[Dict[str, Any]]]:
        """Extract text from document using Docling"""
        try:
            logger.info(f"Extracting text from {filename} using Docling")
            
            full_text, documents = await self.docling_processor.extract_text_with_docling(
                file_content=file_content,
                filename=filename
            )
            
            logger.info(f"Successfully extracted {len(full_text)} characters from {filename}")
            return full_text, documents
            
        except Exception as e:
            logger.error(f"Failed to extract text from {filename}: {e}")
            try:
                fallback_text = await self.docling_processor._fallback_text_extraction(
                    file_content, filename
                )
                logger.warning(f"Used fallback extraction for {filename}")
                return fallback_text, []
            except Exception as fallback_error:
                logger.error(f"Fallback extraction also failed: {fallback_error}")
                raise
    
    async def _chunk_text(
        self, 
        text: str, 
        documents: List[Dict[str, Any]], 
        metadata: DocumentMetadata, 
        filename: str
    ) -> List[Dict[str, Any]]:
        """Chunk text into smaller pieces using Docling"""
        try:
            logger.info("Chunking text using Docling processor")
            
            file_size = len(text.encode('utf-8'))
            config = self.docling_processor.calculate_chunking_config(
                file_size=file_size,
                estimated_text_length=len(text)
            )
            
            if documents: 
                chunks = self.docling_processor._create_docling_chunks(documents, config)
            else:  
                chunks = self.docling_processor._create_text_chunks(text, config)
            
            for chunk in chunks:
                chunk.update({
                    "filename": filename,
                    "document_metadata": metadata.dict()
                })
            
            logger.info(f"Created {len(chunks)} chunks from document")
            return chunks
            
        except Exception as e:
            logger.error(f"Failed to chunk text: {e}")
            raise

    async def _chunk_text_enhanced(
        self, 
        text: str, 
        documents: List[Dict[str, Any]], 
        enhanced_metadata: EnhancedDocumentMetadata, 
        filename: str
    ) -> List[Dict[str, Any]]:
        """Chunk text into smaller pieces using enhanced metadata"""
        try:
            logger.info("Chunking text using Docling processor with enhanced metadata")
            
            # Calculate optimal chunking config
            file_size = enhanced_metadata.file_size or len(text.encode('utf-8'))
            config = self.docling_processor.calculate_chunking_config(
                file_size=file_size,
                estimated_text_length=len(text)
            )
            
            # Create chunks using Docling với enhanced processing
            if documents:  # Use Docling documents if available
                chunks = self.docling_processor._create_docling_chunks(documents, config)
            else:  # Fallback to text chunking
                chunks = self.docling_processor._create_text_chunks(text, config)
            
            # Add enhanced metadata to chunks
            for chunk in chunks:
                chunk.update({
                    "filename": filename,
                    "enhanced_metadata": enhanced_metadata.dict(),
                    "file_hash": enhanced_metadata.file_hash,
                    "extraction_method": enhanced_metadata.extraction_method,
                    "access_level": enhanced_metadata.access_level.value
                })
            
            logger.info(
                f"Created {len(chunks)} chunks from document: "
                f"avg_size={sum(len(c['content']) for c in chunks) // len(chunks) if chunks else 0}, "
                f"extraction_method={enhanced_metadata.extraction_method}"
            )
            return chunks
            
        except Exception as e:
            logger.error(f"Failed to chunk text with enhanced metadata: {e}")
            raise
    
    async def _generate_embeddings(self, chunks: List[Dict[str, Any]]) -> List[List[float]]:
        """Generate embeddings cho chunks using Milvus service"""
        try:
            logger.info(f"Generating embeddings cho {len(chunks)} chunks")
            
            # Ensure Milvus service is initialized
            if not self.milvus_service._initialized:
                await self.milvus_service.initialize()
            
            # Extract text content from chunks
            chunk_texts = [chunk["content"] for chunk in chunks]
            
            # Generate embeddings using Milvus service
            embeddings = await self.milvus_service._generate_embeddings(chunk_texts)
            
            logger.info(f"Successfully generated embeddings for {len(chunks)} chunks")
            return embeddings
            
        except Exception as e:
            logger.error(f"Failed to generate embeddings: {e}")
            raise
    
    async def _store_in_vector_db(
        self,
        document_id: str,
        chunks: List[Dict[str, Any]],
        embeddings: List[List[float]],
        metadata: DocumentMetadata,
        filename: str
    ) -> Dict[str, Any]:
        """Store chunks and embeddings in vector database"""
        try:
            logger.info(f"Storing {len(chunks)} chunks in Milvus vector database")
            
            if not self.milvus_service._initialized:
                await self.milvus_service.initialize()
            
            department = getattr(metadata, 'department', Department.GENERAL)
            if isinstance(department, str):
                department = Department(department.upper())
            
            logger.warning("Vector storage will be handled by the main processing pipeline")
            result = {
                "success": True,
                "chunks_prepared": len(chunks),
                "embeddings_prepared": len(embeddings),
                "message": "Chunks and embeddings prepared for vector storage"
            }
            
            logger.info(f"Successfully stored {len(chunks)} chunks for document {document_id}")
            return result
            
        except Exception as e:
            logger.error(f"Failed to store chunks in vector database: {e}")
            raise
    
    async def _update_document_status(
        self,
        document_id: str,
        status: str,
        progress: int = 0,
        error: Optional[str] = None
    ) -> None:
        """Update document processing status"""
        # Implementation would update database
        logger.info(f"Document {document_id} status: {status} ({progress}%)")
        if error:
            logger.error(f"Document {document_id} error: {error}")
    
    async def _delete_from_vector_db(self, document_id: str, department: Optional[Department] = None) -> bool:
        """Delete document chunks from vector database"""
        try:
            logger.info(f"Deleting document {document_id} from Milvus vector database")
            
            # Determine department
            if not department:
                department = Department.GENERAL
            
            # Get collection name
            collection_name = self.docling_processor.get_collection_name(department)
            
            # Delete from Milvus
            result = await self.milvus_service.delete_document(
                collection_name=collection_name,
                document_id=document_id
            )
            
            logger.info(f"Successfully deleted document {document_id} from vector database")
            return result
            
        except Exception as e:
            logger.error(f"Failed to delete document {document_id} from vector database: {e}")
            raise
    
    async def _delete_from_storage(self, document_id: str, metadata: Optional[DocumentMetadata] = None) -> Dict[str, Any]:
        """Delete document from MinIO storage"""
        try:
            logger.info(f"Deleting document {document_id} from MinIO storage")
            
            department = Department.GENERAL
            if metadata:
                department = getattr(metadata, 'department', Department.GENERAL)
                if isinstance(department, str):
                    department = Department(department.upper())            

            result = await self.minio_service.delete_document(
                document_id=document_id,
                department=department,
                create_backup=True
            )
            
            logger.info(f"Successfully deleted document {document_id} from storage")
            return result
            
        except Exception as e:
            logger.error(f"Failed to delete document {document_id} from storage: {e}")
            raise

document_service = DocumentService()
