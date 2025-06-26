from fastapi import APIRouter, HTTPException, UploadFile, File, Form, BackgroundTasks
from typing import Optional
import asyncio

from models import DocumentMetadata
from models.schemas import (
    DocumentResponse, DocumentSearchRequest, DocumentSearchResponse,
    DocumentStatusResponse, DocumentListResponse, DocumentStatsResponse,
    DocumentDeleteResponse, DocumentReprocessResponse
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
async def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    title: Optional[str] = Form(None),
    author: Optional[str] = Form(None),
    department: Optional[str] = Form(None),
    tags: Optional[str] = Form(""), 
    description: Optional[str] = Form(None),
    language: Optional[str] = Form("vi")
):
    """
    Upload và process document cho RAG system
    """
    try:
        logger.info(f"Processing upload: {file.filename}")
        
        # Parse tags
        tag_list = [tag.strip() for tag in tags.split(",") if tag.strip()] if tags else []
        
        metadata = DocumentMetadata(
            title=title or file.filename,
            author=author,
            department=department,
            tags=tag_list,
            description=description,
            language=language
        )
        
        # Read file content
        file_content = await file.read()
        
        # Handle upload through service layer
        document_id, upload_info = await document_service.upload_document(
            filename=file.filename,
            file_content=file_content,
            metadata=metadata
        )
        
        # Process document in background
        background_tasks.add_task(
            document_service.process_document_async,
            document_id,
            file.filename,
            file_content,
            metadata
        )
        
        return DocumentResponse(
            document_id=document_id,
            filename=file.filename,
            status="processing",
            message="Document được queue để xử lý. Sẽ sớm có sẵn trong hệ thống."
        )
        
    except ServiceError as e:
        logger.error(f"Service error: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Document upload failed: {e}")
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")

@router.post("/search", response_model=DocumentSearchResponse)
@log_performance()
async def search_documents(request: DocumentSearchRequest):
    """
    Search documents trong vector database
    """
    try:
        logger.info(f"Searching documents: {request.query}")
        
        start_time = asyncio.get_event_loop().time()
        
        # Build search filters
        search_filters = {}
        if request.department:
            search_filters["department"] = request.department
        if request.document_type:
            search_filters["document_type"] = request.document_type
        
        # Execute search through service layer
        results = await document_service.search_documents(
            query=request.query,
            top_k=request.top_k,
            threshold=request.threshold,
            filters=search_filters
        )
        
        processing_time = asyncio.get_event_loop().time() - start_time
        
        return DocumentSearchResponse(
            query=request.query,
            results=results,
            total_found=len(results),
            processing_time=processing_time
        )
        
    except ServiceError as e:
        logger.error(f"Service error: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Document search failed: {e}")
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")

@router.get("/status/{document_id}", response_model=DocumentStatusResponse)
async def get_document_status(document_id: str):
    """
    Get processing status của document
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
    """
    List documents với pagination và filtering
    """
    try:
        # Build filters
        filters = {}
        if department:
            filters["department"] = department
        if author:
            filters["author"] = author
        if search:
            filters["search"] = search
        
        # Get documents through service layer
        result = await document_service.list_documents(
            page=page,
            limit=limit,
            filters=filters
        )
        
        return DocumentListResponse(
            documents=result["documents"],
            pagination=result["pagination"],
            filters=filters
        )
        
    except ServiceError as e:
        logger.error(f"Service error: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to list documents: {e}")
        raise HTTPException(status_code=500, detail="Failed to list documents")

@router.delete("/delete/{document_id}", response_model=DocumentDeleteResponse)
async def delete_document(document_id: str, background_tasks: BackgroundTasks):
    """
    Delete document khỏi system
    """
    try:
        logger.info(f"Deleting document: {document_id}")
        
        # Delete document through service layer (in background)
        background_tasks.add_task(document_service.delete_document, document_id)
        
        return DocumentDeleteResponse(
            document_id=document_id,
            status="deletion_queued",
            message="Document deletion has been queued"
        )
        
    except ServiceError as e:
        logger.error(f"Service error: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to delete document: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete document")

@router.post("/reprocess/{document_id}", response_model=DocumentReprocessResponse)
async def reprocess_document(document_id: str, background_tasks: BackgroundTasks):
    """
    Reprocess document với updated settings
    """
    try:
        logger.info(f"Reprocessing document: {document_id}")
        
        # Reprocess document through service layer (in background)
        background_tasks.add_task(document_service.reprocess_document, document_id)
        
        return DocumentReprocessResponse(
            document_id=document_id,
            status="reprocessing_queued",
            message="Document reprocessing has been queued"
        )
        
    except ServiceError as e:
        logger.error(f"Service error: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to reprocess document: {e}")
        raise HTTPException(status_code=500, detail="Failed to reprocess document")

@router.get("/stats", response_model=DocumentStatsResponse)
async def get_document_statistics():
    """
    Get document statistics cho admin dashboard
    """
    try:
        stats = await document_service.get_document_statistics()
        
        return DocumentStatsResponse(
            total_documents=stats["total_documents"],
            processed_documents=stats["processed_documents"],
            processing_documents=stats["processing_documents"],
            failed_documents=stats["failed_documents"],
            total_chunks=stats["total_chunks"],
            storage_used_mb=stats["storage_used_mb"],
            by_department=stats["by_department"],
            by_type=stats["by_type"],
            processing_queue=stats["processing_queue"],
            last_updated=stats["last_updated"]
        )
        
    except ServiceError as e:
        logger.error(f"Service error: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to get document statistics: {e}")
        raise HTTPException(status_code=500, detail="Failed to get document statistics")
