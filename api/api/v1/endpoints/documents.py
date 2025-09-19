"""
Document endpoints for upload, download, and management
"""
import os
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Query
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

from config.database import get_db
from api.v1.middleware.middleware import JWTAuth
from services.documents.document_service import DocumentService
from common.types import DBDocumentPermissionLevel
from utils.logging import get_logger

logger = get_logger(__name__)
router = APIRouter()


@router.post("/upload")
async def upload_document(
    file: UploadFile = File(...),
    collection_name: str = Form(...),
    access_level: str = Form(..., description="public or private"),
    folder_id: Optional[str] = Form(None),
    user_context: dict = Depends(JWTAuth.get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Upload document to specified collection
    """
    try:
        tenant_id = user_context.get("tenant_id")
        user_id = user_context.get("user_id")
        department_id = user_context.get("department_id")

        if not tenant_id or not department_id:
            raise HTTPException(status_code=400, detail="Tenant and department context required")

        if access_level not in ["public", "private"]:
            raise HTTPException(status_code=400, detail="Access level must be 'public' or 'private'")

        db_access_level = (DBDocumentPermissionLevel.PRIVATE
                          if access_level == "private"
                          else DBDocumentPermissionLevel.PUBLIC)

        file_content = await file.read()

        doc_service = DocumentService(db)

        if folder_id:
            result = await doc_service.upload_document_to_folder(
                tenant_id=tenant_id,
                department_id=department_id,
                folder_id=folder_id,
                uploaded_by=user_id,
                file_name=file.filename,
                file_bytes=file_content,
                file_mime_type=file.content_type or "application/octet-stream",
                access_level=db_access_level,
                collection_name=collection_name
            )
        else:
            result = await doc_service.upload_document(
                tenant_id=tenant_id,
                department_id=department_id,
                uploaded_by=user_id,
                file_name=file.filename,
                file_bytes=file_content,
                file_mime_type=file.content_type or "application/octet-stream",
                access_level=db_access_level,
                collection_name=collection_name
            )

        if result and not result.error:
            return {
                "success": True,
                "document_id": result.document_id,
                "file_name": result.file_name,
                "bucket": result.bucket,
                "storage_key": result.storage_key,
                "chunks": result.chunks,
                "collection": collection_name,
                "access_level": access_level
            }
        else:
            raise HTTPException(
                status_code=500,
                detail=result.error if result else "Upload failed"
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Upload failed: {e}")
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")


@router.get("/collections")
async def get_department_collections(
    department_name: str = Query(..., description="Department name"),
    user_context: dict = Depends(JWTAuth.get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get accessible collections for user in department
    """
    try:
        user_id = user_context.get("user_id")

        from services.auth.permission_service import RAGPermissionService

        permission_service = RAGPermissionService(db)
        collections_info = await permission_service.get_user_accessible_collections(
            user_id=user_id,
            department_name=department_name
        )

        return {
            "department": department_name,
            "public_access": collections_info["public_access"],
            "private_access": collections_info["private_access"],
            "accessible_collections": collections_info["all_accessible_collections"],
            "public_collections": collections_info["public_collections"],
            "private_collections": collections_info["private_collections"]
        }

    except Exception as e:
        logger.error(f"Failed to get collections: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get collections: {str(e)}")


@router.post("/folders")
async def create_folder(
    folder_name: str = Form(...),
    parent_folder_id: Optional[str] = Form(None),
    user_context: dict = Depends(JWTAuth.get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Create a new folder (access level will be inherited from parent or default to public)
    """
    try:
        department_id = user_context.get("department_id")

        if not department_id:
            raise HTTPException(status_code=400, detail="Department context required")

        doc_service = DocumentService(db)
        result = await doc_service.create_folder(
            department_id=department_id,
            folder_name=folder_name,
            parent_folder_id=parent_folder_id,
            access_level=None
        )

        if result:
            return {
                "success": True,
                "folder": result
            }
        else:
            raise HTTPException(status_code=500, detail="Failed to create folder")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Create folder failed: {e}")
        raise HTTPException(status_code=500, detail=f"Create folder failed: {str(e)}")


@router.get("/tree")
async def get_folder_tree(
    folder_id: Optional[str] = Query(None, description="Root folder ID, if None uses department root"),
    access_level: Optional[str] = Query(None, description="Filter by access level: public, private, or None for all"),
    user_context: dict = Depends(JWTAuth.get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get folder tree structure with optional access level filter
    """
    try:
        department_id = user_context.get("department_id")

        if not department_id:
            raise HTTPException(status_code=400, detail="Department context required")

        if access_level and access_level not in ["public", "private"]:
            raise HTTPException(status_code=400, detail="Access level must be 'public' or 'private'")

        doc_service = DocumentService(db)
        tree = await doc_service.get_folder_tree(
            department_id=department_id,
            folder_id=folder_id,
            access_level=access_level
        )

        if tree:
            return tree
        else:
            raise HTTPException(status_code=404, detail="Folder tree not found")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get folder tree failed: {e}")
        raise HTTPException(status_code=500, detail=f"Get folder tree failed: {str(e)}")


@router.get("/tree/public")
async def get_public_folder_tree(
    folder_id: Optional[str] = Query(None, description="Root folder ID, if None uses department root"),
    user_context: dict = Depends(JWTAuth.get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get public folder tree structure
    """
    try:
        department_id = user_context.get("department_id")

        if not department_id:
            raise HTTPException(status_code=400, detail="Department context required")

        doc_service = DocumentService(db)
        tree = await doc_service.get_folder_tree(
            department_id=department_id,
            folder_id=folder_id,
            access_level="public"
        )

        if tree:
            return tree
        else:
            raise HTTPException(status_code=404, detail="Public folder tree not found")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get public folder tree failed: {e}")
        raise HTTPException(status_code=500, detail=f"Get public folder tree failed: {str(e)}")


@router.get("/tree/private")
async def get_private_folder_tree(
    folder_id: Optional[str] = Query(None, description="Root folder ID, if None uses department root"),
    user_context: dict = Depends(JWTAuth.get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get private folder tree structure
    """
    try:
        department_id = user_context.get("department_id")

        if not department_id:
            raise HTTPException(status_code=400, detail="Department context required")

        doc_service = DocumentService(db)
        tree = await doc_service.get_folder_tree(
            department_id=department_id,
            folder_id=folder_id,
            access_level="private"
        )

        if tree:
            return tree
        else:
            raise HTTPException(status_code=404, detail="Private folder tree not found")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get private folder tree failed: {e}")
        raise HTTPException(status_code=500, detail=f"Get private folder tree failed: {str(e)}")
