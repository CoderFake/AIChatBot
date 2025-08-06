import asyncio
from typing import Dict, Any, List, Optional, Tuple
from utils.datetime_utils import CustomDateTime as datetime
import uuid

from config.settings import get_settings
from utils.logging import get_logger
from core.exceptions import ServiceError
from models.schemas.requests.document import DocumentRequest
from common.types import FileType

logger = get_logger(__name__)

class DocumentService:

    """
    Service for document management
    Role checking is not implemented here, it is implemented in permission_service.py for document routes
    """

    def __init__(self):
        pass
    
    async def process_document(self, document: DocumentRequest) -> DocumentResponse:
        """
        Process document into db, minio, milvus
        Role: Admin, Dept Admin, Dept Manager
        Kafka: DocumentProcessor
        """
        pass
    
    async def process_document_batch(self, document: ListDocumentRequest)-> ListDocumentResponse:
        """
        Process document batch into db, minio, milvus
        Rollback if any error occurs
        Role: Admin, Dept Admin, Dept Manager
        Kafka: DocumentProcessor
        """
        pass

    async def get_document_progress_percentage(self, document_id: str) -> float:
        """
        Get status percentage progress document
        Role: Admin, Dept Admin, Dept Manager
        Kafka
        """
        pass


    async def get_document_by_id(self, document_id: str) -> DocumenDetailResponse:
        """
        Get document by id
        Role: Admin, Dept Admin, Dept Manager, User
        """
        pass
    
    async def download_document(self, document_id: str):
        """
        Download document from storage Minio
        Role: Admin, Dept Admin, Dept Manager, User
        Kafka: DocumentProcessor
        """
        pass

    async def delete_document(self, document_id: str) -> DocumentResponse:
        """
        Delete document from database and storage Minio, Milvus
        Reindex document in Milvus
        Role: Admin, Dept Admin, Dept Manager
        Kafka: DocumentProcessor
        """
        pass

    async def delete_document_batch(self, document_ids: List[str]) -> ListDocumentResponse:
        """
        Delete document batch from database and storage Minio, Milvus
        Accept error database and storage Minio, Milvus if any error occurs
        Reindex document in Milvus
        Role: Admin, Dept Admin, Dept Manager
        Kafka: DocumentProcessor
        """
        pass
   

document_service = DocumentService()