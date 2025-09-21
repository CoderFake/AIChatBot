"""
Document endpoints for upload, download, and management
"""
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Body
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import and_, select

from config.database import get_db
from api.v1.middleware.middleware import JWTAuth, RequireAtLeastDeptManager
from services.documents.document_service import DocumentService
from utils.logging import get_logger
from models.database.document import Document
from common.types import validate_file_type

logger = get_logger(__name__)
router = APIRouter()


# ==========================================
# FOLDER OPERATIONS
# ==========================================

@router.post("/folders")
async def create_folder(
    folder_name: str = Form(...),
    parent_folder_id: Optional[str] = Form(None),
    access_level: Optional[str] = Form("public", description="Access level: public or private"),
    user_context: dict = Depends(RequireAtLeastDeptManager()),
    db: AsyncSession = Depends(get_db)
):
    """
    Create a new folder with specified access level
    """
    try:
        user_role = user_context.get("role")
        department_id = user_context.get("department_id")

        if not department_id and user_role != "ADMIN":
            raise HTTPException(status_code=400, detail="Department context required")

        if access_level not in ["public", "private"]:
            raise HTTPException(status_code=400, detail="Access level must be 'public' or 'private'")

        from common.types import DocumentAccessLevel
        db_access_level = (DocumentAccessLevel.PRIVATE
                          if access_level == "private"
                          else DocumentAccessLevel.PUBLIC)

        doc_service = DocumentService(db)
        result = await doc_service.create_folder(
            department_id=department_id,
            folder_name=folder_name,
            parent_folder_id=parent_folder_id,
            access_level=db_access_level,
            user_role=user_role
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


@router.get("/folders")
async def get_folders(
    folder_id: Optional[str] = None,
    user_context: dict = Depends(JWTAuth.get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get folders with role-based access control according to get_info_doc.md

    Query parameters:
    - folder_id: Optional folder ID to get specific folder + children. If not provided, returns root folders
    """
    try:
        tenant_id = user_context.get("tenant_id")
        user_role = user_context.get("role")
        user_department_id = user_context.get("department_id")

        if not tenant_id:
            raise HTTPException(status_code=400, detail="Tenant context required")

        if not user_department_id and user_role == "ADMIN":
            from models.database.tenant import Department
            dept_result = await db.execute(
                select(Department).where(Department.tenant_id == tenant_id).limit(1)
            )
            department = dept_result.scalar_one_or_none()
            if department:
                user_department_id = str(department.id)

        if not user_department_id:
            raise HTTPException(status_code=400, detail="Department context required")

        doc_service = DocumentService(db)
        result = await doc_service.get_folders(
            role=user_role,
            department_id=user_department_id,
            folder_id=folder_id
        )

        return {
            "success": True,
            "data": result,
            "count": len(result)
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get folders failed: {e}")
        raise HTTPException(status_code=500, detail=f"Get folders failed: {str(e)}")


@router.put("/folders/{folder_id}")
async def update_folder(
    folder_id: str,
    request: dict,
    user_context: dict = Depends(JWTAuth.get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Update folder information (name, access_level)
    """
    try:
        tenant_id = user_context.get("tenant_id")
        user_role = user_context.get("role")
        department_id = user_context.get("department_id")

        if not department_id and user_role == "ADMIN":
            from models.database.tenant import Department

            dept_result = await db.execute(
                select(Department).where(Department.tenant_id == tenant_id).limit(1)
            )
            department = dept_result.scalar_one_or_none()
            if department:
                department_id = str(department.id)

        if not department_id:
            raise HTTPException(status_code=400, detail="Department context required")

        if user_role not in ["ADMIN", "DEPT_ADMIN"]:
            raise HTTPException(status_code=403, detail="Insufficient permissions to update folders")

        from models.database.document import DocumentFolder
        folder_result = await db.execute(
            select(DocumentFolder).where(
                and_(
                    DocumentFolder.id == folder_id,
                    DocumentFolder.department_id == department_id
                )
            )
        )
        folder = folder_result.scalar_one_or_none()

        if not folder:
            raise HTTPException(status_code=404, detail="Folder not found")

        # Update fields
        updates = {}
        if "folder_name" in request and request["folder_name"]:
            updates["folder_name"] = request["folder_name"]
        if "access_level" in request and request["access_level"] in ["public", "private"]:
            updates["access_level"] = request["access_level"]

        if not updates:
            raise HTTPException(status_code=400, detail="No valid fields to update")

        # Update folder
        for key, value in updates.items():
            setattr(folder, key, value)

        await db.commit()

        return {
            "success": True,
            "folder": {
                "id": str(folder.id),
                "folder_name": folder.folder_name,
                "folder_path": folder.folder_path,
                "access_level": folder.access_level
            },
            "message": "Folder updated successfully"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Update folder failed: {e}")
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Update folder failed: {str(e)}")


@router.put("/folders/{folder_id}/rename")
async def rename_folder(
    folder_id: str,
    rename_data: dict = Body(..., example={"new_name": "new_folder_name"}),
    user_context: dict = Depends(JWTAuth.get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Rename a folder
    """
    try:
        tenant_id = user_context.get("tenant_id")
        user_role = user_context.get("role")

        if not tenant_id:
            raise HTTPException(status_code=400, detail="Tenant context required")

        new_name = rename_data.get("new_name")
        if not new_name or not new_name.strip():
            raise HTTPException(status_code=400, detail="New name is required")

        doc_service = DocumentService(db)
        result = await doc_service.rename_folder(
            folder_id=folder_id,
            new_name=new_name.strip(),
            user_role=user_role,
            user_department_id=user_context.get("department_id"),
            tenant_id=tenant_id
        )

        return {
            "success": True,
            "message": "Folder renamed successfully",
            "folder": result
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Rename folder failed: {e}")
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Rename folder failed: {str(e)}")


@router.put("/folders/{folder_id}/move")
async def move_folder(
    folder_id: str,
    request: dict,
    user_context: dict = Depends(JWTAuth.get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Move folder to different parent folder
    """
    try:
        tenant_id = user_context.get("tenant_id")
        user_role = user_context.get("role")
        department_id = user_context.get("department_id")

        if not department_id and user_role == "ADMIN":
            from models.database.tenant import Department

            dept_result = await db.execute(
                select(Department).where(Department.tenant_id == tenant_id).limit(1)
            )
            department = dept_result.scalar_one_or_none()
            if department:
                department_id = str(department.id)

        if not department_id:
            raise HTTPException(status_code=400, detail="Department context required")

        # Validate permissions
        if user_role not in ["ADMIN", "DEPT_ADMIN"]:
            raise HTTPException(status_code=403, detail="Insufficient permissions to move folders")

        target_parent_id = request.get("target_parent_id")
        if not target_parent_id:
            raise HTTPException(status_code=400, detail="Target parent folder ID required")

        # Validate both folders exist and belong to department
        from models.database.document import DocumentFolder
        folder_result = await db.execute(
            select(DocumentFolder).where(
                and_(
                    DocumentFolder.id == folder_id,
                    DocumentFolder.department_id == department_id
                )
            )
        )
        folder = folder_result.scalar_one_or_none()

        if not folder:
            raise HTTPException(status_code=404, detail="Source folder not found")

        # Prevent moving to itself or its children
        if str(folder.id) == target_parent_id:
            raise HTTPException(status_code=400, detail="Cannot move folder to itself")

        # Check if target is a child of the folder being moved
        current_parent = target_parent_id
        while current_parent:
            if current_parent == str(folder.id):
                raise HTTPException(status_code=400, detail="Cannot move folder to its own child")
            parent_result = await db.execute(
                select(DocumentFolder).where(DocumentFolder.id == current_parent)
            )
            parent = parent_result.scalar_one_or_none()
            if parent:
                current_parent = str(parent.parent_folder_id) if parent.parent_folder_id else None
            else:
                break

        # Update parent folder
        folder.parent_folder_id = target_parent_id

        # Update folder path
        if target_parent_id:
            parent_result = await db.execute(
                select(DocumentFolder).where(DocumentFolder.id == target_parent_id)
            )
            parent = parent_result.scalar_one_or_none()
            if parent:
                folder.folder_path = f"{parent.folder_path.rstrip('/')}/{folder.folder_name}/"
            else:
                raise HTTPException(status_code=404, detail="Target parent folder not found")
        else:
            folder.folder_path = f"/{folder.folder_name}/"

        await db.commit()

        return {
            "success": True,
            "folder": {
                "id": str(folder.id),
                "folder_name": folder.folder_name,
                "folder_path": folder.folder_path,
                "parent_folder_id": str(folder.parent_folder_id) if folder.parent_folder_id else None
            },
            "message": "Folder moved successfully"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Move folder failed: {e}")
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Move folder failed: {str(e)}")


@router.delete("/folders/{folder_id}")
async def delete_folder(
    folder_id: str,
    user_context: dict = Depends(JWTAuth.get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Delete a folder and all its contents (requires admin or dept_admin role)
    """
    try:
        department_id = user_context.get("department_id")
        user_role = user_context.get("role")

        if not department_id:
            raise HTTPException(status_code=400, detail="Department context required")

        if user_role not in ["ADMIN", "DEPT_ADMIN"]:
            raise HTTPException(status_code=403, detail="Insufficient permissions to delete folders")

        doc_service = DocumentService(db)

        from models.database.document import DocumentFolder

        result = await db.execute(
            select(DocumentFolder).where(
                and_(
                    DocumentFolder.id == folder_id,
                    DocumentFolder.department_id == department_id
                )
            )
        )
        folder = result.scalar_one_or_none()

        if not folder:
            raise HTTPException(status_code=404, detail="Folder not found")

        # Check if it's a root folder
        if folder.folder_path == "/":
            raise HTTPException(status_code=400, detail="Cannot delete root folder")

        # Delete folder and all contents
        success = await doc_service.delete_folder(folder_id, department_id)

        if success:
            return {"success": True, "message": "Folder deleted successfully"}
        else:
            raise HTTPException(status_code=500, detail="Failed to delete folder")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Delete folder failed: {e}")
        raise HTTPException(status_code=500, detail=f"Delete folder failed: {str(e)}")


# ==========================================
# DOCUMENT OPERATIONS
# ==========================================

@router.post("/upload")
async def upload_document(
    file: UploadFile = File(...),
    folder_id: str = Form(None),
    user_context: dict = Depends(RequireAtLeastDeptManager()),
    db: AsyncSession = Depends(get_db)
):
    """
    Upload document (default collection: documents, access level: public)
    """
    try:
        tenant_id = user_context.get("tenant_id")
        user_id = user_context.get("user_id")
        user_role = user_context.get("role")
        department_id = user_context.get("department_id")

        if user_role != "ADMIN" and not department_id:
            raise HTTPException(status_code=400, detail="Tenant and department context required")

        # Validate file type using common utility
        file_mime_type = file.content_type or "application/octet-stream"
        try:
            file_type_short = validate_file_type(file_mime_type)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))

        file_content = await file.read()
        doc_service = DocumentService(db)

        result = await doc_service.upload_document(
            tenant_id=tenant_id,
            department_id=department_id,
            file_folder_id=folder_id,
            uploaded_by=user_id,
            file_name=file.filename,
            file_bytes=file_content,
            file_mime_type=file_type_short
        )

        if result and not result.error:
            return {
                "success": True,
                "document_id": result.document_id,
                "file_name": result.file_name,
                "bucket": result.bucket,
                "storage_key": result.storage_key,
                "chunks": result.chunks
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


@router.post("/upload/batch")
async def upload_multiple_documents(
    files: List[UploadFile] = File(...),
    folder_id: Optional[str] = Form(None),
    user_context: dict = Depends(JWTAuth.get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Upload multiple documents in batch (default collection: documents, access level: public)
    """
    try:
        tenant_id = user_context.get("tenant_id")
        user_id = user_context.get("user_id")
        user_role = user_context.get("role")
        department_id = user_context.get("department_id")

        # Handle department assignment for ADMIN users
        if not department_id and user_role == "ADMIN":
            from models.database.tenant import Department

            dept_result = await db.execute(
                select(Department).where(Department.tenant_id == tenant_id).limit(1)
            )
            department = dept_result.scalar_one_or_none()
            if department:
                department_id = str(department.id)

        if not tenant_id or not department_id:
            raise HTTPException(status_code=400, detail="Tenant and department context required")

        # Validate permissions
        if user_role not in ["ADMIN", "DEPT_ADMIN", "DEPT_MANAGER"]:
            raise HTTPException(status_code=403, detail="Insufficient permissions to upload")

        if not files or len(files) == 0:
            raise HTTPException(status_code=400, detail="No files provided")

        if len(files) > 10: 
            raise HTTPException(status_code=400, detail="Maximum 10 files per batch upload")

        file_data = []
        for file in files:
            file_mime_type = file.content_type or "application/octet-stream"
            try:
                file_type_short = validate_file_type(file_mime_type)
            except ValueError as e:
                raise HTTPException(
                    status_code=400,
                    detail=f"File '{file.filename}' has unsupported type: {str(e)}"
                )

            file_content = await file.read()
            file_data.append((
                file.filename,
                file_content,
                file_type_short 
            ))

        doc_service = DocumentService(db)

        results = await doc_service.batch_upload_documents(
            tenant_id=tenant_id,
            department_id=department_id,
            uploaded_by=user_id,
            files=file_data,
            file_folder_id=folder_id
        )

        successful = []
        failed = []

        for result in results:
            if result and hasattr(result, 'document_id') and result.document_id:
                successful.append({
                    "document_id": result.document_id,
                    "file_name": result.file_name,
                    "bucket": result.bucket,
                    "storage_key": result.storage_key
                })
            else:
                failed.append({
                    "file_name": getattr(result, 'file_name', 'Unknown'),
                    "error": getattr(result, 'error', 'Upload failed')
                })

        return {
            "success": len(successful) > 0,
            "total_files": len(files),
            "successful": successful,
            "failed": failed
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Batch upload failed: {e}")
        raise HTTPException(status_code=500, detail=f"Batch upload failed: {str(e)}")


@router.put("/{document_id}")
async def update_document(
    document_id: str,
    request: dict,
    user_context: dict = Depends(JWTAuth.get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Update document information
    """
    try:
        tenant_id = user_context.get("tenant_id")
        user_role = user_context.get("role")
        department_id = user_context.get("department_id")

        if not department_id and user_role == "ADMIN":
            from models.database.tenant import Department

            dept_result = await db.execute(
                select(Department).where(Department.tenant_id == tenant_id).limit(1)
            )
            department = dept_result.scalar_one_or_none()
            if department:
                department_id = str(department.id)

        if not department_id:
            raise HTTPException(status_code=400, detail="Department context required")

        # Validate permissions
        if user_role not in ["ADMIN", "DEPT_ADMIN"]:
            raise HTTPException(status_code=403, detail="Insufficient permissions to update documents")

        # Get document
        doc_result = await db.execute(
            select(Document).where(
                and_(
                    Document.id == document_id,
                    Document.department_id == department_id
                )
            )
        )
        doc = doc_result.scalar_one_or_none()

        if not doc:
            raise HTTPException(status_code=404, detail="Document not found")

        # Update fields
        updates = {}
        if "title" in request and request["title"]:
            updates["title"] = request["title"]
        if "description" in request and request["description"] is not None:
            updates["description"] = request["description"]
        if "access_level" in request and request["access_level"] in ["public", "private"]:
            updates["access_level"] = request["access_level"]

        if not updates:
            raise HTTPException(status_code=400, detail="No valid fields to update")

        # Update document
        for key, value in updates.items():
            setattr(doc, key, value)

        await db.commit()

        return {
            "success": True,
            "document": {
                "id": str(doc.id),
                "filename": doc.filename,
                "title": doc.title,
                "description": doc.description,
                "access_level": doc.access_level
            },
            "message": "Document updated successfully"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Update document failed: {e}")
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Update document failed: {str(e)}")


@router.put("/{document_id}/rename")
async def rename_document(
    document_id: str,
    rename_data: dict = Body(..., example={"new_name": "new_document_name.pdf"}),
    user_context: dict = Depends(JWTAuth.get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Rename a document
    """
    try:
        tenant_id = user_context.get("tenant_id")
        user_role = user_context.get("role")

        if not tenant_id:
            raise HTTPException(status_code=400, detail="Tenant context required")

        new_name = rename_data.get("new_name")
        if not new_name or not new_name.strip():
            raise HTTPException(status_code=400, detail="New name is required")

        doc_service = DocumentService(db)
        result = await doc_service.rename_document(
            document_id=document_id,
            new_name=new_name.strip(),
            user_role=user_role,
            user_department_id=user_context.get("department_id"),
            tenant_id=tenant_id
        )

        return {
            "success": True,
            "message": "Document renamed successfully",
            "document": result
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Rename document failed: {e}")
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Rename document failed: {str(e)}")


@router.put("/{document_id}/move")
async def move_document(
    document_id: str,
    request: dict,
    user_context: dict = Depends(JWTAuth.get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Move document to different folder
    """
    try:
        tenant_id = user_context.get("tenant_id")
        user_role = user_context.get("role")
        department_id = user_context.get("department_id")

        if not department_id and user_role == "ADMIN":
            from models.database.tenant import Department

            dept_result = await db.execute(
                select(Department).where(Department.tenant_id == tenant_id).limit(1)
            )
            department = dept_result.scalar_one_or_none()
            if department:
                department_id = str(department.id)

        if not department_id:
            raise HTTPException(status_code=400, detail="Department context required")

        # Validate permissions
        if user_role not in ["ADMIN", "DEPT_ADMIN", "DEPT_MANAGER"]:
            raise HTTPException(status_code=403, detail="Insufficient permissions to move documents")

        target_folder_id = request.get("target_folder_id")
        if target_folder_id is None:
            raise HTTPException(status_code=400, detail="Target folder ID required")

        # Get document
        doc_result = await db.execute(
            select(Document).where(
                and_(
                    Document.id == document_id,
                    Document.department_id == department_id
                )
            )
        )
        doc = doc_result.scalar_one_or_none()

        if not doc:
            raise HTTPException(status_code=404, detail="Document not found")

        if not target_folder_id:
            doc.folder_id = None
        else:
            from models.database.document import DocumentFolder
            folder_result = await db.execute(
                select(DocumentFolder).where(
                    and_(
                        DocumentFolder.id == target_folder_id,
                        DocumentFolder.department_id == department_id
                    )
                )
            )
            folder = folder_result.scalar_one_or_none()

            if not folder:
                raise HTTPException(status_code=404, detail="Target folder not found")

            doc.folder_id = target_folder_id

        await db.commit()

        return {
            "success": True,
            "document": {
                "id": str(doc.id),
                "filename": doc.filename,
                "title": doc.title,
                "folder_id": str(doc.folder_id) if doc.folder_id else None
            },
            "message": "Document moved successfully"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Move document failed: {e}")
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Move document failed: {str(e)}")


@router.get("/{document_id}/download")
async def download_document(
    document_id: str,
    user_context: dict = Depends(JWTAuth.get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Download a document
    """
    try:
        from fastapi.responses import Response

        doc_service = DocumentService(db)
        result = await doc_service.download_document(document_id)

        if result:
            data, mime_type, filename = result
            return Response(
                content=data,
                media_type=mime_type,
                headers={"Content-Disposition": f"attachment; filename={filename}"}
            )
        else:
            raise HTTPException(status_code=404, detail="Document not found")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Download document failed: {e}")
        raise HTTPException(status_code=500, detail=f"Download document failed: {str(e)}")


@router.delete("/{document_id}")
async def delete_document(
    document_id: str,
    user_context: dict = Depends(JWTAuth.get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Delete a document (requires admin or dept_admin role)
    """
    try:
        department_id = user_context.get("department_id")
        tenant_id = user_context.get("tenant_id")
        user_role = user_context.get("role")

        if not department_id or not tenant_id:
            raise HTTPException(status_code=400, detail="Tenant and department context required")

        # Check permissions
        if user_role not in ["ADMIN", "DEPT_ADMIN"]:
            raise HTTPException(status_code=403, detail="Insufficient permissions to delete documents")

        doc_service = DocumentService(db)
        result = await doc_service.delete_document(tenant_id, department_id, document_id)

        if result.deleted:
            response = {"success": True, "message": "Document deleted successfully"}
            if result.errors:
                response["warnings"] = result.errors
            return response
        else:
            if result.error == "not_found":
                raise HTTPException(status_code=404, detail="Document not found")
            else:
                raise HTTPException(status_code=500, detail=result.error)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Delete document failed: {e}")
        raise HTTPException(status_code=500, detail=f"Delete document failed: {str(e)}")


# ==========================================
# PROGRESS OPERATIONS
# ==========================================

@router.get("/progress/{document_id}")
async def get_document_progress(
    document_id: str,
    user_context: dict = Depends(JWTAuth.get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get document processing progress from Kafka
    Returns real-time progress for document upload/processing
    """
    try:
        tenant_id = user_context.get("tenant_id")
        department_id = user_context.get("department_id")

        if not tenant_id:
            raise HTTPException(status_code=400, detail="Tenant context required")

        from services.messaging.kafka_service import document_progress_service

        result = await document_progress_service.get_document_progress(
            tenant_id=tenant_id,
            department_id=department_id,
            document_id=document_id,
            db=db
        )

        if isinstance(result, dict) and "error" in result:
            raise HTTPException(
                status_code=result.get("status_code", 500),
                detail=result["error"]
            )

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get document progress failed: {e}")
        raise HTTPException(status_code=500, detail=f"Get document progress failed: {str(e)}")


@router.get("/progress/batch/{batch_id}")
async def get_batch_progress(
    batch_id: str,
    user_context: dict = Depends(JWTAuth.get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get batch upload progress from Kafka
    Returns real-time progress for batch operations
    """
    try:
        tenant_id = user_context.get("tenant_id")
        department_id = user_context.get("department_id")

        if not tenant_id or not department_id:
            raise HTTPException(status_code=400, detail="Tenant and department context required")

        from services.messaging.kafka_service import document_progress_service

        result = await document_progress_service.get_batch_progress(
            tenant_id=tenant_id,
            department_id=department_id,
            batch_id=batch_id
        )

        if isinstance(result, dict) and "error" in result:
            raise HTTPException(
                status_code=result.get("status_code", 500),
                detail=result["error"]
            )

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get batch progress failed: {e}")
        raise HTTPException(status_code=500, detail=f"Get batch progress failed: {str(e)}")


@router.get("/progress/realtime")
async def get_realtime_progress(
    user_context: dict = Depends(JWTAuth.get_current_user)
):
    """
    Get real-time progress stream from Kafka
    Returns latest progress updates for all user's documents
    """
    try:
        tenant_id = user_context.get("tenant_id")
        department_id = user_context.get("department_id")

        if not tenant_id or not department_id:
            raise HTTPException(status_code=400, detail="Tenant and department context required")

        # Use document progress service
        from services.messaging.kafka_service import document_progress_service

        result = await document_progress_service.get_realtime_progress(
            tenant_id=tenant_id,
            department_id=department_id
        )

        if isinstance(result, dict) and "error" in result:
            raise HTTPException(
                status_code=result.get("status_code", 500),
                detail=result["error"]
            )

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get realtime progress failed: {e}")
        raise HTTPException(status_code=500, detail=f"Get realtime progress failed: {str(e)}")

