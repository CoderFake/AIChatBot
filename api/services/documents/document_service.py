from typing import Optional, Dict, Any, List, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import and_, select, delete
from sqlalchemy.orm import selectinload
from utils.logging import get_logger
from utils.datetime_utils import DateTimeManager
import asyncio
import tempfile
import os
from uuid import uuid4

from models.database.tenant import Department
from models.database.document import DocumentFolder, DocumentCollection, Document
from services.vector.milvus_service import milvus_service
from services.messaging.kafka_service import kafka_service
from services.storage.minio_service import minio_service
from common.types import (
    DBDocumentPermissionLevel, 
    DocumentAccessLevel, 
    DocumentProcessingStatus,
    VectorProcessingStatus,
    KafkaMessageStatus,
    DocumentConstants
)
from common.dataclasses import (
    DocumentUploadResult, 
    BatchUploadProgress,
    DocumentDeleteResult
)
from config.settings import get_settings
from utils.file_processor import FileProcessor

logger = get_logger(__name__)
settings = get_settings()


class DocumentService:
    """
    Document service for creating department root folder and Milvus collections.
    - Root folder: one per department with folder_path "/"
    - Collections: {tenant_id}-{department_id}-public/private
    Fully async with AsyncSession

    Extended CRUD for documents with transactional upload, batch upload, delete, download, detail, update.
    Progress is reported 1-100% via Kafka in realtime.
    """

    def __init__(self, db_session: AsyncSession):
        self.db: AsyncSession = db_session
        self.file_processor = FileProcessor(
            tokenizer_name=settings.embedding.model_name,
            max_tokens=getattr(settings.embedding, 'max_length', 1500),
            enable_hybrid_chunking=True,
        )

    async def _ensure_milvus_collections(self, public_name: str, private_name: str) -> None:
        """Best-effort ensure Milvus collections exist using milvus_service (async)."""
        try:
            await asyncio.gather(
                milvus_service.ensure_collection_exists(
                    collection_name=public_name,
                    access_level=DocumentAccessLevel.PUBLIC.value,
                ),
                milvus_service.ensure_collection_exists(
                    collection_name=private_name,
                    access_level=DBDocumentPermissionLevel.PRIVATE.value,
                ),
            )
        except Exception as e:
            logger.warning(f"Milvus ensure collections failed: {e}")

    async def create_folder(
        self,
        department_id: str,
        folder_name: str,
        parent_folder_id: Optional[str] = None,
        access_level: Optional[DocumentAccessLevel] = None,
        created_by: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """Create a new folder in the hierarchy"""
        try:
            parent_folder = None
            if parent_folder_id:
                parent_result = await self.db.execute(
                    select(DocumentFolder).where(DocumentFolder.id == parent_folder_id)
                )
                parent_folder: Optional[DocumentFolder] = parent_result.scalar_one_or_none()
                if not parent_folder:
                    raise ValueError("Parent folder does not exist")

            if parent_folder:
                existing_result = await self.db.execute(
                    select(DocumentFolder).where(
                        and_(
                            DocumentFolder.department_id == department_id,
                            DocumentFolder.parent_folder_id == parent_folder_id,
                            DocumentFolder.folder_name == folder_name
                        )
                    )
                )
            else:
                existing_result = await self.db.execute(
                    select(DocumentFolder).where(
                        and_(
                            DocumentFolder.department_id == department_id,
                            DocumentFolder.parent_folder_id.is_(None),
                            DocumentFolder.folder_name == folder_name
                        )
                    )
                )

            if existing_result.scalar_one_or_none():
                raise ValueError(f"Folder with name '{folder_name}' already exists")

            if parent_folder:
                folder_path = f"{parent_folder.folder_path}/{folder_name}"
            else:
                folder_path = f"/{folder_name}"

            new_folder = DocumentFolder(
                department_id=department_id,
                folder_name=folder_name,
                folder_path=folder_path,
                parent_folder_id=parent_folder_id,
                access_level=access_level
            )

            self.db.add(new_folder)
            await self.db.flush()

            if not parent_folder_id:
                await self.db.commit()

            return {
                "id": str(new_folder.id),
                "folder_name": new_folder.folder_name,
                "folder_path": new_folder.folder_path,
                "parent_folder_id": str(new_folder.parent_folder_id) if new_folder.parent_folder_id else None,
                "access_level": new_folder.access_level,
                "created_at": new_folder.created_at.isoformat() if new_folder.created_at else None
            }
            
        except Exception as e:
            logger.error(f"Failed to create folder: {e}")
            await self.db.rollback()
            return None

    async def get_root_folder(self, department_id: str, access_level: str) -> Optional[DocumentFolder]:
        """Get a folder by department ID and folder name"""
        root_folder = await self.db.execute(
            select(DocumentFolder)
            .where(
                and_(
                    DocumentFolder.department_id == department_id,
                    DocumentFolder.parent_folder_id.is_(None),
                    DocumentFolder.access_level == access_level
                )
            )
        )
        root_folder = root_folder.scalar_one_or_none()
        return root_folder

    async def get_folders(
        self,
        role: str,
        department_id: str,
        folder_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Get folders with role-based access control according to get_info_doc.md

        Args:
            role: User role (USER, DEPT_ADMIN, DEPT_MANAGER, ADMIN)
            department_id: Department ID for filtering
            folder_id: Specific folder ID to get (None for root folders)

        Returns:
            List of folder dictionaries with documents and subfolders
        """
        results = []

        try:
            if folder_id is None:
                root_query = select(DocumentFolder).where(DocumentFolder.parent_folder_id.is_(None))

                if role == "USER":
                    root_query = root_query.where(DocumentFolder.access_level == "public")
                elif role in ["DEPT_ADMIN", "DEPT_MANAGER"]:
                    root_query = root_query.where(
                        (DocumentFolder.department_id == department_id) |
                        ((DocumentFolder.department_id != department_id) & (DocumentFolder.access_level == "public"))
                    )

                root_folders = (await self.db.execute(root_query)).scalars().all()

                for folder in root_folders:
                    results.append({
                        "id": str(folder.id),
                        "folder_name": folder.folder_name,
                        "folder_path": folder.folder_path,
                        "parent_folder_id": None,
                        "created_at": folder.created_at.isoformat() if folder.created_at else None,
                        "updated_at": folder.updated_at.isoformat() if folder.updated_at else None,
                        "documents": [], 
                        "subfolders": []  
                    })

            else:
                folder = await self.db.get(DocumentFolder, folder_id)
                if not folder:
                    logger.warning(f"Folder {folder_id} not found")
                    return []

                can_access = False
                if role == "ADMIN":
                    can_access = True
                elif role == "USER":
                    can_access = folder.access_level == "public"
                elif role in ["DEPT_ADMIN", "DEPT_MANAGER"]:
                    can_access = (str(folder.department_id) == department_id or folder.access_level == "public")

                if not can_access:
                    logger.warning(f"Access denied for folder {folder_id} with role {role}")
                    return []

                subfolders_query = select(DocumentFolder).where(DocumentFolder.parent_folder_id == folder_id)
                if role == "USER":
                    subfolders_query = subfolders_query.where(DocumentFolder.access_level == "public")
                elif role in ["DEPT_ADMIN", "DEPT_MANAGER"]:
                    subfolders_query = subfolders_query.where(
                        (DocumentFolder.department_id == department_id) |
                        ((DocumentFolder.department_id != department_id) & (DocumentFolder.access_level == "public"))
                    )
                subfolders = (await self.db.execute(subfolders_query)).scalars().all()

                documents_query = select(Document).where(Document.folder_id == folder_id)
                if role == "USER":
                    documents_query = documents_query.where(Document.access_level == "public")
                elif role in ["DEPT_ADMIN", "DEPT_MANAGER"]:
                    documents_query = documents_query.where(
                        (Document.department_id == department_id) |
                        ((Document.department_id != department_id) & (Document.access_level == "public"))
                    )
                documents = (await self.db.execute(documents_query)).scalars().all()

                folder_response = {
                    "id": str(folder.id),
                    "folder_name": folder.folder_name,
                    "folder_path": folder.folder_path,
                    "parent_folder_id": str(folder.parent_folder_id) if folder.parent_folder_id else None,
                    "created_at": folder.created_at.isoformat() if folder.created_at else None,
                    "updated_at": folder.updated_at.isoformat() if folder.updated_at else None,
                    "documents": [
                        {
                            "id": str(doc.id),
                            "name": doc.filename,  
                            "folder_id": str(doc.folder_id),
                            "created_at": doc.created_at.isoformat() if doc.created_at else None,
                            "updated_at": doc.updated_at.isoformat() if doc.updated_at else None,
                        }
                        for doc in documents
                    ],
                    "subfolders": [
                        {
                            "id": str(sub.id),
                            "folder_name": sub.folder_name,
                            "folder_path": sub.folder_path,
                            "parent_folder_id": str(sub.parent_folder_id) if sub.parent_folder_id else None,
                            "created_at": sub.created_at.isoformat() if sub.created_at else None,
                            "updated_at": sub.updated_at.isoformat() if sub.updated_at else None,
                            "documents": [],  # Direct children only
                            "subfolders": []  # Direct children only
                        }
                        for sub in subfolders
                    ]
                }

                results.append(folder_response)

            logger.info(f"Retrieved {len(results)} folders for role {role}, department {department_id}")
            return results

        except Exception as e:
            logger.error(f"Failed to get folders: {e}")
            return []

    async def delete_folder(self, folder_id: str, department_id: str) -> bool:
        """
        Delete a folder and all its contents recursively
        """
        try:
            result = await self.db.execute(
                select(DocumentFolder).where(
                    and_(
                        DocumentFolder.id == folder_id,
                        DocumentFolder.department_id == department_id
                    )
                )
            )
            folder = result.scalar_one_or_none()
            if not folder:
                return False

            subfolders_result = await self.db.execute(
                select(DocumentFolder).where(DocumentFolder.parent_folder_id == folder_id)
            )
            subfolders = subfolders_result.scalars().all()

            for subfolder in subfolders:
                await self.delete_folder(str(subfolder.id), department_id)

            documents_result = await self.db.execute(
                select(Document).where(Document.folder_id == folder_id)
            )
            documents = documents_result.scalars().all()

            for doc in documents:
                try:
                    await minio_service.delete_object(doc.bucket_name, doc.storage_key)

                    if doc.collection_id:
                        collection_result = await self.db.execute(
                            select(DocumentCollection).where(DocumentCollection.id == doc.collection_id)
                        )
                        collection = collection_result.scalar_one_or_none()
                        if collection:
                            await milvus_service.delete_document_vectors(
                                collection_name=collection.collection_name,
                                document_id=str(doc.id)
                            )
                except Exception as e:
                    logger.warning(f"Failed to delete document {doc.id} storage/vector data: {e}")

            await self.db.execute(
                delete(Document).where(Document.folder_id == folder_id)
            )

            await self.db.execute(
                delete(DocumentFolder).where(DocumentFolder.id == folder_id)
            )
            
            await self.db.commit()
            return True

        except Exception as e:
            logger.error(f"Failed to delete folder {folder_id}: {e}")
            await self.db.rollback()
            return False

    async def create_collection(
        self,
        department_id: str,
        collection_name: str,
        collection_type: str = DocumentAccessLevel.PUBLIC.value,
        commit: bool = False
    ) -> Optional[DocumentCollection]:
        """Create a new collection"""
        try:
            new_collection = DocumentCollection(
                department_id=department_id,
                collection_name=DocumentConstants.sanitize_identifier(collection_name),
                collection_type=collection_type,
                is_active=True,
                vector_config=None,
                document_count=0,
            )
            self.db.add(new_collection)
            await self.db.flush()
            if commit:
                await self.db.commit()
            return new_collection
        except Exception as e:
            logger.error(f"Failed to create collection: {e}")
            await self.db.rollback()
            return None

    async def get_collection(self, department_id: str, collection_name: str, collection_type: str) -> Optional[DocumentCollection]:
        """Get a collection by department ID and collection name"""
        normalized_name = DocumentConstants.sanitize_identifier(collection_name)
        collection = await self.db.execute(
            select(DocumentCollection)
            .where(
                DocumentCollection.department_id == department_id,
                DocumentCollection.collection_name == normalized_name,
                DocumentCollection.collection_type == collection_type
            )
        )
        collection = collection.scalar_one_or_none()
        return collection

    # ------------------- Helper methods -------------------

    def _build_bucket_name(self, tenant_id: str) -> str:
        """Build bucket name from tenant ID using settings"""
        return DocumentConstants.BUCKET_NAME_TEMPLATE.format(
            prefix=settings.storage.bucket_prefix,
            tenant_id=tenant_id
        )


    def _build_storage_key(self, tenant_id: str, department_id: str, document_uuid: str, filename: str) -> str:
        """Build storage key for MinIO using document UUID, access level and recursive folder path"""
        return DocumentConstants.STORAGE_KEY_TEMPLATE.format(
            tenant_id=tenant_id,
            department_id=department_id,
            document_uuid=document_uuid,
            filename=os.path.basename(filename)
        )

    async def _publish_progress(self, tenant_id: str, department_id: str, document_id: Optional[str], 
                                progress: int, status: KafkaMessageStatus, message: str, 
                                extra: Optional[Dict[str, Any]] = None) -> None:
        """Publish progress via Kafka service"""
        await kafka_service.publish_document_progress(
            tenant_id=tenant_id,
            department_id=department_id,
            document_id=document_id,
            progress=progress,
            status=status.value,
            message=message,
            extra=extra
        )

    async def _index_to_milvus(self, collection_name: str, chunks: List[Any], base_meta: Dict[str, Any], access: str) -> int:
        """Index document chunks to Milvus"""
        try:
            milvus_instance = settings.MILVUS_PRIVATE_HOST if access == "private" else settings.MILVUS_PUBLIC_HOST

            count = await milvus_service.index_document_chunks(
                collection_name=collection_name,
                chunks=chunks,
                metadata=base_meta,
                milvus_instance=milvus_instance,
            )
            return int(count or 0)
        except Exception as e:
            logger.error(f"Milvus indexing failed: {e}")
            raise

    # ------------------- CRUD methods -------------------

    async def _rollback_upload(
        self,
        tenant_id: str,
        department_id: str,
        doc: Optional[Document],
        bucket: str,
        storage_key: Optional[str],
        collection_name: Optional[str],
        document_id: Optional[str],
        access_level: Optional[str],
        chunks_created: bool = False
    ) -> None:
        """Complete rollback of failed upload: DB -> MinIO -> Milvus"""
        logger.info(f"Starting complete rollback for document {document_id}")

        # 1. Rollback database
        try:
            await self.db.rollback()
            logger.info("Database transaction rolled back")
        except Exception as e:
            logger.error(f"Failed to rollback database: {e}")

        # 2. Delete from MinIO
        if storage_key:
            try:
                await minio_service.delete_object(bucket, storage_key)
                logger.info(f"Deleted file from MinIO: {storage_key}")
            except Exception as e:
                logger.error(f"Failed to delete from MinIO: {e}")

        # 3. Delete from Milvus if chunks were created
        if chunks_created and collection_name and document_id:
            try:
                milvus_instance = getattr(settings, 'MILVUS_PRIVATE_HOST', 'milvus_private') if access_level == "private" else getattr(settings, 'MILVUS_PUBLIC_HOST', 'milvus_public')
                await milvus_service.bulk_delete_by_filter(
                    collection_name=collection_name,
                    milvus_instance=milvus_instance,
                    filter_expr=f"document_id == '{document_id}'"
                )
                logger.info(f"Deleted vectors from Milvus collection {collection_name} for document {document_id}")
            except Exception as e:
                logger.error(f"Failed to delete from Milvus: {e}")

        # 4. Publish rollback completion
        try:
            await self._publish_progress(
                tenant_id, department_id, document_id,
                DocumentConstants.PROGRESS_COMPLETED,
                KafkaMessageStatus.FAILED,
                "Upload failed and rolled back completely"
            )
        except Exception as e:
            logger.error(f"Failed to publish rollback progress: {e}")

    async def upload_document(
        self,
        tenant_id: str,
        department_id: str,
        file_folder_id: str,
        uploaded_by: str,
        file_name: str,
        file_bytes: bytes,
        file_mime_type: str
    ) -> Optional[DocumentUploadResult]:
        """
        Transactional upload with complete rollback: MinIO -> DB -> Milvus.
        If any step fails, rollback ALL: MinIO + DB + Milvus.
        Progress is published to Kafka.
        """
        bucket = self._build_bucket_name(tenant_id)
        doc: Optional[Document] = None
        storage_key: Optional[str] = None
        collection_name: Optional[str] = None
        access_level: Optional[str] = None
        chunks_created: bool = False
        document_id: Optional[str] = None

        try:
            await self._publish_progress(
                tenant_id, department_id, None,
                DocumentConstants.PROGRESS_START,
                KafkaMessageStatus.PROCESSING,
                "Starting upload"
            )

            # Step 1: Get folder and collection info
            folder_result = await self.db.execute(
                select(DocumentFolder.access_level, DocumentFolder.department_id)
                .where(DocumentFolder.id == file_folder_id)
            )

            row = folder_result.one_or_none()
            if row:
                access_level, department_id = row
            else:
                raise ValueError(f"Folder {file_folder_id} not found")

            department_id_str = str(department_id)
            collection_name = DocumentConstants.format_collection_name(department_id_str, access_level)
            result = await self.db.execute(
                select(DocumentCollection).where(
                    DocumentCollection.department_id == department_id,
                    DocumentCollection.collection_name == collection_name
                )
            )
            collection: Optional[DocumentCollection] = result.scalar_one_or_none()
            if not collection:
                raise ValueError(f"Collection {collection_name} not found")

            # Step 2: Create DB record
            title = os.path.splitext(os.path.basename(file_name))[0]
            doc = Document(
                filename=file_name,
                title=title,
                description=file_name,
                department_id=department_id,
                folder_id=str(file_folder_id),
                collection_id=str(collection.id),
                uploaded_by=uploaded_by,
                access_level=access_level,
                file_size=len(file_bytes),
                file_type=file_mime_type,
                storage_key="",
                bucket_name=bucket,
                processing_status=DocumentProcessingStatus.PROCESSING.value,
                vector_status=VectorProcessingStatus.PENDING.value
            )
            self.db.add(doc)
            await self.db.flush()

            document_id = str(doc.id)
            storage_key = self._build_storage_key(tenant_id, department_id, document_id, file_name)
            doc.storage_key = storage_key
            await self.db.flush()

            await self._publish_progress(
                tenant_id, department_id, document_id,
                DocumentConstants.PROGRESS_DB_CREATED,
                KafkaMessageStatus.PROCESSING,
                "Created DB record"
            )

            # Step 3: Upload to MinIO
            await minio_service.ensure_bucket(bucket)
            await minio_service.put_bytes(bucket, storage_key, file_bytes, file_mime_type)
            await self._publish_progress(
                tenant_id, department_id, document_id,
                DocumentConstants.PROGRESS_STORAGE_UPLOADED,
                KafkaMessageStatus.PROCESSING,
                "Uploaded to storage"
            )

            # Step 4: Process file chunks
            with tempfile.TemporaryDirectory() as tmpdir:
                tmp_path = os.path.join(tmpdir, os.path.basename(file_name))
                with open(tmp_path, "wb") as f:
                    f.write(file_bytes)
                chunks = await self.file_processor.process_file(
                    file_path=tmp_path,
                    file_name=file_name,
                    doc_id=document_id,
                    metadata={"department_id": department_id, "collection_name": collection.collection_name}
                )
            await self._publish_progress(
                tenant_id, department_id, document_id,
                DocumentConstants.PROGRESS_CHUNKS_EXTRACTED,
                KafkaMessageStatus.PROCESSING,
                "Extracted chunks"
            )

            # Step 5: Index to Milvus
            base_meta = {"document_id": document_id, "department_id": department_id}
            indexed = await self._index_to_milvus(collection.collection_name, chunks, base_meta, access_level)
            chunks_created = True

            # Step 6: Update status and commit
            doc.processing_status = DocumentProcessingStatus.COMPLETED.value
            doc.vector_status = VectorProcessingStatus.COMPLETED.value
            doc.chunk_count = int(indexed)
            await self.db.flush()
            await self.db.commit()

            await self._publish_progress(
                tenant_id, department_id, document_id,
                DocumentConstants.PROGRESS_COMPLETED,
                KafkaMessageStatus.COMPLETED,
                "Ingestion completed",
                {"chunks": indexed}
            )

            return DocumentUploadResult(
                document_id=document_id,
                file_name=file_name,
                bucket=bucket,
                storage_key=storage_key,
                chunks=indexed,
                status=DocumentProcessingStatus.COMPLETED.value,
            )

        except Exception as e:
            logger.error(f"Upload failed: {e}")
            # Complete rollback of all components
            await self._rollback_upload(
                tenant_id=tenant_id,
                department_id=department_id,
                doc=doc,
                bucket=bucket,
                storage_key=storage_key,
                collection_name=collection_name,
                document_id=document_id,
                access_level=access_level,
                chunks_created=chunks_created
            )
            return DocumentUploadResult(error=str(e))

    async def batch_upload_documents(
        self,
        tenant_id: str,
        department_id: str,
        uploaded_by: str,
        files: List[Tuple[str, bytes, str]],
        access_level: DBDocumentPermissionLevel,
        collection_name: str,
        base_metadata: Optional[Dict[str, Any]] = None,
        file_folder_id: Optional[str] = None
    ) -> List[DocumentUploadResult]:
        """
        Batch upload: concurrent processing; each file is its own transactional flow.
        """
        batch_progress = BatchUploadProgress(
            batch_id=str(uuid4()),
            tenant_id=tenant_id,
            department_id=department_id,
            total_files=len(files)
        )
        
        await kafka_service.publish_batch_progress(
            tenant_id=tenant_id,
            department_id=department_id,
            batch_id=batch_progress.batch_id,
            total_files=batch_progress.total_files,
            completed_files=0,
            failed_files=0,
            status=KafkaMessageStatus.PROCESSING.value,
            message=f"Starting batch upload of {batch_progress.total_files} files"
        )

        sem = asyncio.Semaphore(DocumentConstants.DEFAULT_BATCH_SEMAPHORE_LIMIT)

        async def _worker(f_name: str, f_bytes: bytes, f_type: str) -> DocumentUploadResult:
            async with sem:
                res = await self.upload_document(
                    tenant_id=tenant_id,
                    department_id=department_id,
                    file_folder_id=file_folder_id,
                    uploaded_by=uploaded_by,
                    file_name=f_name,
                    file_bytes=f_bytes,
                    file_mime_type=f_type,
                    access_level=access_level,
                    collection_name=collection_name,
                    metadata=base_metadata or {},
                )
                
                if res and res.status == DocumentProcessingStatus.COMPLETED.value:
                    batch_progress.completed_files += 1
                else:
                    batch_progress.failed_files += 1
                
                await kafka_service.publish_batch_progress(
                    tenant_id=tenant_id,
                    department_id=department_id,
                    batch_id=batch_progress.batch_id,
                    total_files=batch_progress.total_files,
                    completed_files=batch_progress.completed_files,
                    failed_files=batch_progress.failed_files,
                    status=KafkaMessageStatus.PROCESSING.value,
                    message=f"Processed {batch_progress.completed_files + batch_progress.failed_files}/{batch_progress.total_files} files"
                )
                
                return res or DocumentUploadResult(file_name=f_name, error="Upload failed")

        tasks = [_worker(name, content, mime) for (name, content, mime) in files]
        results = await asyncio.gather(*tasks, return_exceptions=False)
    
        final_status = (KafkaMessageStatus.COMPLETED if batch_progress.failed_files == 0 
                       else KafkaMessageStatus.COMPLETED_WITH_ERRORS)
        await kafka_service.publish_batch_progress(
            tenant_id=tenant_id,
            department_id=department_id,
            batch_id=batch_progress.batch_id,
            total_files=batch_progress.total_files,
            completed_files=batch_progress.completed_files,
            failed_files=batch_progress.failed_files,
            status=final_status.value,
            message=f"Batch upload completed: {batch_progress.completed_files} success, {batch_progress.failed_files} failed"
        )
        
        return results

    async def delete_document(self, tenant_id: str, department_id: str, document_id: str) -> DocumentDeleteResult:
        """
        Best-effort delete: minio -> db -> milvus(reindex). If any step fails, still accept with error details.
        """
        errors: List[str] = []
        
        try:
            result = await self.db.execute(select(Document).where(Document.id == document_id))
            doc: Optional[Document] = result.scalar_one_or_none()
            if not doc:
                return DocumentDeleteResult(
                    document_id=document_id, 
                    deleted=False, 
                    error="not_found"
                )

            await self._publish_progress(
                tenant_id, department_id, document_id, 
                DocumentConstants.PROGRESS_START, 
                KafkaMessageStatus.PROCESSING, 
                "Deleting from storage"
            )

            try:
                await minio_service.delete_object(doc.bucket_name, doc.storage_key)
            except Exception as e:
                errors.append(f"minio: {e}")
            await self._publish_progress(
                tenant_id, department_id, document_id, 
                DocumentConstants.PROGRESS_STORAGE_DELETED, 
                KafkaMessageStatus.PROCESSING, 
                "Storage deleted"
            )

            try:
                await self.db.execute(delete(Document).where(Document.id == document_id))
                await self.db.commit()
            except Exception as e:
                await self.db.rollback()
                errors.append(f"db: {e}")
            await self._publish_progress(
                tenant_id, department_id, document_id, 
                DocumentConstants.PROGRESS_DB_DELETED, 
                KafkaMessageStatus.PROCESSING, 
                "DB deleted"
            )

            try:
                await milvus_service.delete_document_vectors(
                    collection_name=str(doc.collection.collection_name), 
                    document_id=document_id
                )
            except Exception as e:
                errors.append(f"milvus: {e}")

            status = (KafkaMessageStatus.COMPLETED if not errors 
                     else KafkaMessageStatus.COMPLETED_WITH_ERRORS)
            await self._publish_progress(
                tenant_id, department_id, document_id, 
                DocumentConstants.PROGRESS_COMPLETED, 
                status, 
                "Delete finished", 
                {"errors": errors}
            )
            return DocumentDeleteResult(
                document_id=document_id, 
                deleted=True, 
                errors=errors
            )
            
        except Exception as e:
            logger.error(f"Delete document failed: {e}")
            await self._publish_progress(
                tenant_id, department_id, document_id, 
                DocumentConstants.PROGRESS_COMPLETED, 
                KafkaMessageStatus.FAILED, 
                str(e)
            )
            return DocumentDeleteResult(
                document_id=document_id, 
                deleted=False, 
                error=str(e)
            )

    async def download_document(self, document_id: str) -> Optional[Tuple[bytes, str, str]]:
        """Download object from MinIO and return (data_bytes, mime_type, file_name)."""
        try:
            result = await self.db.execute(select(Document).where(Document.id == document_id))
            doc: Optional[Document] = result.scalar_one_or_none()
            if not doc:
                return None
            data = await minio_service.get_bytes(doc.bucket_name, doc.storage_key)
            return data, doc.file_type, doc.filename
        except Exception as e:
            logger.error(f"Download failed for {document_id}: {e}")
            return None

    async def get_document_detail(self, document_id: str) -> Optional[Dict[str, Any]]:
        """Get document metadata detail."""
        try:
            result = await self.db.execute(select(Document).where(Document.id == document_id))
            doc: Optional[Document] = result.scalar_one_or_none()
            if not doc:
                return None
            return {
                "id": str(doc.id),
                "filename": doc.filename,
                "title": doc.title,
                "description": doc.description,
                "department_id": str(doc.department_id),
                "folder_id": str(doc.folder_id) if doc.folder_id else None,
                "collection_id": str(doc.collection_id) if doc.collection_id else None,
                "uploaded_by": str(doc.uploaded_by),
                "access_level": doc.access_level,
                "file_size": doc.file_size,
                "file_type": doc.file_type,
                "bucket_name": doc.bucket_name,
                "storage_key": doc.storage_key,
                "processing_status": doc.processing_status,
                "vector_status": doc.vector_status,
                "metadata": doc.metadata or {},
                "chunk_count": doc.chunk_count,
                "created_at": doc.created_at.isoformat() if doc.created_at else None,
                "updated_at": doc.updated_at.isoformat() if doc.updated_at else None,
            }
        except Exception as e:
            logger.error(f"Get detail failed: {e}")
            return None

    # ------------------- Department & Access Level Operations -------------------


    # ------------------- Rename Operations -------------------

    async def rename_document(
        self,
        document_id: str,
        new_name: str,
        user_role: str = "USER",
        user_department_id: Optional[str] = None,
        tenant_id: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """Rename a document"""
        try:
            logger.info(f"DocumentService.rename_document: document_id={document_id}, new_name={new_name}, user_role={user_role}")

            # Get document
            doc_result = await self.db.execute(
                select(Document).where(Document.id == document_id)
            )
            document = doc_result.scalar_one_or_none()

            if not document:
                raise ValueError("Document not found")

            # Check permissions - ADMIN can rename any document, others can only rename in their department
            if user_role != "ADMIN":
                if str(document.department_id) != user_department_id:
                    raise ValueError("Cannot rename document from different department")

            # Update document name
            document.filename = new_name.strip()
            document.title = new_name.strip()
            document.updated_at = await DateTimeManager.tenant_now_cached(tenant_id, self.db)

            await self.db.commit()

            return {
                "id": str(document.id),
                "filename": document.filename,
                "title": document.title
            }

        except Exception as e:
            logger.error(f"Failed to rename document {document_id}: {e}")
            await self.db.rollback()
            raise

    async def rename_folder(
        self,
        folder_id: str,
        new_name: str,
        user_role: str = "USER",
        user_department_id: Optional[str] = None,
        tenant_id: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """Rename a folder"""
        try:
            logger.info(f"DocumentService.rename_folder: folder_id={folder_id}, new_name={new_name}, user_role={user_role}")

            # Get folder
            folder_result = await self.db.execute(
                select(DocumentFolder).where(DocumentFolder.id == folder_id)
            )
            folder = folder_result.scalar_one_or_none()

            if not folder:
                raise ValueError("Folder not found")

            if user_role != "ADMIN":
                if str(folder.department_id) != user_department_id:
                    raise ValueError("Cannot rename folder from different department")

            folder.folder_name = new_name.strip()
            folder.updated_at = await DateTimeManager.tenant_now_cached(tenant_id, self.db)

            await self.db.commit()

            return {
                "id": str(folder.id),
                "folder_name": folder.folder_name
            }

        except Exception as e:
            logger.error(f"Failed to rename folder {folder_id}: {e}")
            await self.db.rollback()
            raise

        """Get detailed information about a specific folder with full context"""
        try:
            logger.info(f"DocumentService.get_folder: folder_id={folder_id}")

            # Get the folder
            folder_result = await self.db.execute(
                select(DocumentFolder).where(DocumentFolder.id == folder_id)
            )
            folder = folder_result.scalar_one_or_none()

            if not folder:
                return None

            # Get department info
            dept_result = await self.db.execute(
                select(Department).where(Department.id == folder.department_id)
            )
            department = dept_result.scalar_one_or_none()

            if not department:
                raise ValueError("Department not found")

            # Build context
            context = {
                "department_id": str(folder.department_id),
                "folder_id": folder_id,
                "role": "user",  # This would be passed from the calling context
                "department_name": department.name,
                "is_root": folder.parent_folder_id is None,
                "queried_at": DateTimeManager.utc_now().isoformat()
            }

            # Get breadcrumbs (full path to this folder)
            breadcrumbs = []
            current_folder_id = folder_id
            path_parts = []

            while current_folder_id:
                current_result = await self.db.execute(
                    select(DocumentFolder).where(DocumentFolder.id == current_folder_id)
                )
                current_folder = current_result.scalar_one_or_none()

                if not current_folder:
                    break

                path_parts.insert(0, {
                    "id": str(current_folder.id),
                    "name": current_folder.folder_name,
                    "path_display": await self._build_path_display(str(current_folder.department_id), str(current_folder.id))
                })

                current_folder_id = str(current_folder.parent_folder_id) if current_folder.parent_folder_id else None

            # Add department to breadcrumbs
            breadcrumbs = [{
                "id": str(department.id),
                "name": department.name,
                "path_display": department.name
            }] + path_parts

            # Get child folders
            child_folders_result = await self.db.execute(
                select(DocumentFolder).where(DocumentFolder.parent_folder_id == folder_id)
            )
            child_folders = child_folders_result.scalars().all()

            # Get documents in this folder
            docs_result = await self.db.execute(
                select(Document).options(selectinload(Document.collection)).where(
                    Document.folder_id == folder_id
                )
            )
            documents = docs_result.scalars().all()

            # Build folder child IDs
            folder_child_ids = [str(f.id) for f in child_folders]

            # Build document IDs
            document_ids = [str(d.id) for d in documents]

            # Format child folders
            folders = []
            for child_folder in child_folders:
                path_display = await self._build_path_display(str(department.id), str(child_folder.id))

                folders.append({
                    "id": str(child_folder.id),
                    "department_id": str(child_folder.department_id),
                    "folder_name": child_folder.folder_name,
                    "folder_path": child_folder.folder_path,
                    "path_display": path_display,
                    "parent_folder_id": str(child_folder.parent_folder_id) if child_folder.parent_folder_id else None,
                    "access_level": child_folder.access_level,
                    "created_by": str(child_folder.created_by) if child_folder.created_by else None,
                    "created_at": child_folder.created_at.isoformat() if child_folder.created_at else None,
                    "updated_at": child_folder.updated_at.isoformat() if child_folder.updated_at else None
                })

            # Format documents
            documents_formatted = []
            for doc in documents:
                path_display = await self._build_document_path_display(str(department.id), folder_id, doc.filename)

                # Get collection info
                collection_info = None
                if doc.collection:
                    collection_info = {
                        "id": str(doc.collection.id),
                        "collection_name": doc.collection.collection_name,
                        "collection_type": doc.collection.collection_type,
                        "is_active": doc.collection.is_active,
                        "vector_config": doc.collection.vector_config,
                        "document_count": doc.collection.document_count
                    }

                documents_formatted.append({
                    "id": str(doc.id),
                    "department_id": str(doc.department_id),
                    "folder_id": str(doc.folder_id) if doc.folder_id else None,
                    "collection_id": str(doc.collection_id) if doc.collection_id else None,
                    "title": doc.title or doc.filename,
                    "filename": doc.filename,
                    "description": doc.description,
                    "access_level": doc.access_level,
                    "uploaded_by": str(doc.uploaded_by) if doc.uploaded_by else None,
                    "file_size": doc.file_size,
                    "file_type": doc.file_type,
                    "bucket_name": doc.bucket_name,
                    "storage_key": doc.storage_key,
                    "storage_path": doc.storage_path,
                    "processing_status": doc.processing_status,
                    "vector_status": doc.vector_status,
                    "chunk_count": doc.chunk_count,
                    "collection": collection_info,
                    "path_display": path_display,
                    "permissions": {
                        "can_access": True,  # Simplified - would need proper permission check
                        "reason": "folder_access"
                    },
                    "created_at": doc.created_at.isoformat() if doc.created_at else None,
                    "updated_at": doc.updated_at.isoformat() if doc.updated_at else None
                })

            # Get counts
            total_folders = len(folders)
            total_documents = len(documents_formatted)

            return {
                "context": context,
                "folder_child_ids": folder_child_ids,
                "document_ids": document_ids,
                "breadcrumbs": breadcrumbs,
                "folders": folders,
                "documents": documents_formatted,
                "counts": {
                    "folders": total_folders,
                    "documents": total_documents
                },
                "pagination": {
                    "page": 1,
                    "page_size": 50,
                    "total_folders": total_folders,
                    "total_documents": total_documents
                }
            }

        except Exception as e:
            logger.error(f"Failed to get folder {folder_id}: {e}")
            return None
