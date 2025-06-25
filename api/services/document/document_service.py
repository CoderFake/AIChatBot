import asyncio
from typing import Dict, Any, List, Optional, Tuple
from utils.datetime_utils import CustomDateTime as datetime
import uuid

from schemas.document_schemas import DocumentMetadata
from config.settings import get_settings
from utils.logging import get_logger
from core.exceptions import ServiceError

logger = get_logger(__name__)
settings = get_settings()

class DocumentService:
    """
    Service layer cho document processing
    Tách biệt business logic khỏi API endpoints
    """
    
    def __init__(self):
        self.processing_tasks = {}  
    
    async def upload_document(
        self,
        filename: str,
        file_content: bytes,
        metadata: DocumentMetadata
    ) -> Tuple[str, Dict[str, Any]]:
        """
        Handle document upload và queue processing
        
        Returns:
            Tuple[document_id, upload_info]
        """
        try:
            # Generate document ID
            document_id = str(uuid.uuid4())
            
            # Validate file
            self._validate_file(filename, file_content)
            
            # Store upload info
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
        Background processing cho document
        """
        try:
            logger.info(f"Starting background processing cho document {document_id}")
            
            # Update status to processing
            await self._update_document_status(document_id, "processing", 0)
            
            # Step 1: Save to storage (MinIO)
            await self._save_to_storage(document_id, filename, file_content)
            await self._update_document_status(document_id, "processing", 20)
            
            # Step 2: Extract text from document
            extracted_text = await self._extract_text(filename, file_content)
            await self._update_document_status(document_id, "processing", 40)
            
            # Step 3: Chunk the text
            chunks = await self._chunk_text(extracted_text, metadata)
            await self._update_document_status(document_id, "processing", 60)
            
            # Step 4: Generate embeddings
            embeddings = await self._generate_embeddings(chunks)
            await self._update_document_status(document_id, "processing", 80)
            
            # Step 5: Store in vector database
            await self._store_in_vector_db(document_id, chunks, embeddings, metadata)
            await self._update_document_status(document_id, "completed", 100)
            
            result = {
                "document_id": document_id,
                "status": "completed",
                "chunk_count": len(chunks),
                "processing_time": 0.0  # Would track actual time
            }
            
            logger.info(f"Document {document_id} processed successfully với {len(chunks)} chunks")
            return result
            
        except Exception as e:
            logger.error(f"Failed to process document {document_id}: {e}")
            await self._update_document_status(document_id, "failed", error=str(e))
            raise ServiceError(f"Document processing failed: {str(e)}")
    
    async def search_documents(
        self,
        query: str,
        top_k: int = 5,
        threshold: float = 0.3,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Search documents trong vector database
        """
        try:
            from services.vector.milvus_service import milvus_service
            
            # Execute search
            results = await milvus_service.search(
                query=query,
                top_k=top_k,
                threshold=threshold,
                filters=filters or {}
            )
            
            return results
            
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
        List documents với pagination và filtering
        """
        try:
            # In real implementation, query from database
            # For now, return placeholder data
            
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
                    "created_at": datetime.now().isoformat(),
                    "tags": ["sample", "test"]
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
            
            # Delete from vector database
            await self._delete_from_vector_db(document_id)
            
            # Delete from file storage
            await self._delete_from_storage(document_id)
            
            # Update document status in database
            await self._update_document_status(document_id, "deleted")
            
            return {
                "document_id": document_id,
                "status": "deleted",
                "message": "Document deleted successfully"
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
            
            # Get document content from storage
            # Delete old chunks from vector database
            # Reprocess with current settings
            # Store new chunks
            
            # Placeholder implementation
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
    
    # Private helper methods
    def _validate_file(self, filename: str, file_content: bytes) -> None:
        """Validate uploaded file"""
        supported_types = [".pdf", ".docx", ".txt", ".md"]
        file_ext = f".{filename.lower().split('.')[-1]}" if "." in filename else ""
        
        if file_ext not in supported_types:
            raise ValueError(f"Unsupported file type. Supported: {supported_types}")
        
        # Check file size
        max_size_mb = settings.MAX_FILE_SIZE_MB
        if len(file_content) > max_size_mb * 1024 * 1024:
            raise ValueError(f"File too large. Max size: {max_size_mb}MB")
    
    async def _save_to_storage(self, document_id: str, filename: str, file_content: bytes) -> None:
        """Save file to MinIO storage"""
        # Implementation would use MinIO service
        logger.info(f"Saving document {document_id} to storage")
        await asyncio.sleep(0.1)  # Simulate I/O
    
    async def _extract_text(self, filename: str, file_content: bytes) -> str:
        """Extract text from document"""
        # Implementation would use appropriate text extraction based on file type
        logger.info(f"Extracting text from {filename}")
        await asyncio.sleep(0.5)  # Simulate processing
        return "Extracted text content..."
    
    async def _chunk_text(self, text: str, metadata: DocumentMetadata) -> List[Dict[str, Any]]:
        """Chunk text into smaller pieces"""
        # Implementation would use LangChain text splitters
        logger.info("Chunking text into smaller pieces")
        await asyncio.sleep(0.3)  # Simulate processing
        
        # Placeholder chunks
        chunks = []
        for i in range(5):
            chunks.append({
                "chunk_id": f"chunk_{i}",
                "content": f"Chunk content {i}...",
                "metadata": metadata.dict()
            })
        return chunks
    
    async def _generate_embeddings(self, chunks: List[Dict[str, Any]]) -> List[List[float]]:
        """Generate embeddings cho chunks"""
        # Implementation would use embedding service
        logger.info(f"Generating embeddings cho {len(chunks)} chunks")
        await asyncio.sleep(0.5)  # Simulate processing
        
        # Placeholder embeddings
        return [[0.1] * 1024 for _ in chunks]
    
    async def _store_in_vector_db(
        self,
        document_id: str,
        chunks: List[Dict[str, Any]],
        embeddings: List[List[float]],
        metadata: DocumentMetadata
    ) -> None:
        """Store chunks and embeddings in vector database"""
        # Implementation would use Milvus service
        logger.info(f"Storing {len(chunks)} chunks in vector database")
        await asyncio.sleep(0.3)  # Simulate processing
    
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
    
    async def _delete_from_vector_db(self, document_id: str) -> None:
        """Delete document chunks from vector database"""
        logger.info(f"Deleting document {document_id} from vector database")
        await asyncio.sleep(0.2)  # Simulate processing
    
    async def _delete_from_storage(self, document_id: str) -> None:
        """Delete document from file storage"""
        logger.info(f"Deleting document {document_id} from storage")
        await asyncio.sleep(0.1)  # Simulate processing

# Global instance
document_service = DocumentService()
