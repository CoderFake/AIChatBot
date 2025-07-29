import asyncio
from typing import Dict, Any, List, Optional, Tuple
from utils.datetime_utils import CustomDateTime as datetime
import uuid

from config.settings import get_settings
from utils.logging import get_logger
from core.exceptions import ServiceError
from models.schemas.requests.document import DocumentRequest
from common.types import Department, FileType

logger = get_logger(__name__)

class DocumentService:
    def __init__(self):
        pass
    
    async def process_document(self, document: DocumentRequest):
        pass
    
    async def process_document_batch(self, document: DocumentRequest):
        pass

    async def get_document_by_id(self, document_id: str):
        pass
    
    
   

document_service = DocumentService()