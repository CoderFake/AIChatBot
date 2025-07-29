from fastapi import APIRouter, HTTPException, UploadFile, File, Form, BackgroundTasks
from typing import Optional
import asyncio

from models.schemas.responses.document import (
    DocumentResponse,
    DocumentStatusResponse, 
    DocumentDetailResponse,
    DocumentListResponse,
    DocumentDeleteResponse
)
from services.document.document_service import document_service
from config.settings import get_settings
from core.exceptions import ServiceError
from utils.logging import get_logger, log_performance

router = APIRouter()
logger = get_logger(__name__)
settings = get_settings()

@router.post("/upload", response_model=DocumentResponse)
@log_performance()
async def upload_document():
   """
   Check auth, permission
   Validate file type, size
   """
   pass

@router.post("/upload/multiple", response_model=DocumentResponse)
@log_performance()
async def upload_multiple_document():
   """
   Check auth, permission
   Validate file type, size
   """
   pass


@router.get("/document/{document_id}", response_model=DocumentDetailResponse)
@log_performance()
async def get_document_by_id():
   """
   Check auth, permission
   Validate file type, size
   """
   pass


@router.get("/status/{document_id}", response_model=DocumentStatusResponse)
async def get_document_status(document_id: str):
    """
    Get processing status of document
    """
    try:
        status_info = await document_service.get_document_status(document_id)
        
        return DocumentStatusResponse(
            document_id=status_info["document_id"],
            status=status_info["status"],
            processing_progress=status_info["processing_progress"],
            chunk_count=status_info.get("chunk_count"),
            created_at=status_info["created_at"],
            processed_at=status_info.get("processed_at"),
            error=status_info.get("error")
        )
        
    except ServiceError as e:
        logger.error(f"Service error: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to get document status: {e}")
        raise HTTPException(status_code=500, detail="Failed to get document status")

@router.get("/list", response_model=DocumentListResponse)
async def list_documents(
    page: int = 1,
    limit: int = 20,
    department: Optional[str] = None,
    author: Optional[str] = None,
    search: Optional[str] = None
):
   pass

@router.delete("/delete/{document_id}", response_model=DocumentDeleteResponse)
async def delete_document():
    """
    Delete document from system
    check auth, permission
    """
    pass
