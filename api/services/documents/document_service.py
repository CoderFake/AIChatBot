from typing import Optional, Dict, Any, List, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import and_, select, delete
from utils.logging import get_logger
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
    DocumentUploadRequest,
    DocumentUploadResult, 
    DocumentProgressEvent,
    BatchUploadProgress,
    DocumentDeleteResult,
    MilvusCollectionInfo
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
                    milvus_instance=DBDocumentPermissionLevel.PUBLIC.value,
                ),
                milvus_service.ensure_collection_exists(
                    collection_name=private_name,
                    milvus_instance=DBDocumentPermissionLevel.PRIVATE.value,
                ),
            )
        except Exception as e:
            logger.warning(f"Milvus ensure collections failed: {e}")

    async def create_department_root(self, tenant_id: str, department_id: str) -> Optional[Dict[str, str]]:
        """
        Create root folders and two collections (public/private) for a department.
        Creates separate root folders for public and private access levels.
        Returns dict with document_root_ids and collection names if success.
        """
        try:
            result = await self.db.execute(select(Department).where(Department.id == department_id))
            department: Optional[Department] = result.scalar_one_or_none()
            if not department:
                logger.error(f"Department {department_id} not found for document root")
                return None

            # Create or get public root folder
            result = await self.db.execute(
                select(DocumentFolder).where(
                    and_(
                        DocumentFolder.department_id == department_id,
                        DocumentFolder.folder_path == DocumentConstants.ROOT_FOLDER_PATH,
                        DocumentFolder.access_level == DocumentAccessLevel.PUBLIC.value,
                    )
                )
            )
            existing_public_root: Optional[DocumentFolder] = result.scalar_one_or_none()

            if existing_public_root:
                public_root_folder = existing_public_root
            else:
                public_root_folder = DocumentFolder(
                    department_id=department_id,
                    folder_name=f"{DocumentConstants.ROOT_FOLDER_NAME}_public",
                    folder_path=DocumentConstants.ROOT_FOLDER_PATH,
                    access_level=DocumentAccessLevel.PUBLIC.value,
                )
                self.db.add(public_root_folder)

            # Create or get private root folder
            result = await self.db.execute(
                select(DocumentFolder).where(
                    and_(
                        DocumentFolder.department_id == department_id,
                        DocumentFolder.folder_path == DocumentConstants.ROOT_FOLDER_PATH,
                        DocumentFolder.access_level == DocumentAccessLevel.PRIVATE.value,
                    )
                )
            )
            existing_private_root: Optional[DocumentFolder] = result.scalar_one_or_none()

            if existing_private_root:
                private_root_folder = existing_private_root
            else:
                private_root_folder = DocumentFolder(
                    department_id=department_id,
                    folder_name=f"{DocumentConstants.ROOT_FOLDER_NAME}_private",
                    folder_path=DocumentConstants.ROOT_FOLDER_PATH,
                    access_level=DocumentAccessLevel.PRIVATE.value,
                )
                self.db.add(private_root_folder)

            await self.db.flush()

            public_name = DocumentConstants.COLLECTION_NAME_TEMPLATE_PUBLIC.format(
                tenant_id=tenant_id, department_id=department_id
            )
            private_name = DocumentConstants.COLLECTION_NAME_TEMPLATE_PRIVATE.format(
                tenant_id=tenant_id, department_id=department_id
            )

            result = await self.db.execute(
                select(DocumentCollection).where(
                    and_(
                        DocumentCollection.department_id == department_id,
                        DocumentCollection.collection_type == DBDocumentPermissionLevel.PUBLIC.value,
                    )
                )
            )
            existing_public: Optional[DocumentCollection] = result.scalar_one_or_none()
            if not existing_public:
                public_collection = DocumentCollection(
                    department_id=department_id,
                    collection_name=public_name,
                    collection_type=DBDocumentPermissionLevel.PUBLIC.value,
                    is_active=True,
                )
                self.db.add(public_collection)
            else:
                public_name = existing_public.collection_name

            result = await self.db.execute(
                select(DocumentCollection).where(
                    and_(
                        DocumentCollection.department_id == department_id,
                        DocumentCollection.collection_type == DBDocumentPermissionLevel.PRIVATE.value,
                    )
                )
            )
            existing_private: Optional[DocumentCollection] = result.scalar_one_or_none()
            if not existing_private:
                private_collection = DocumentCollection(
                    department_id=department_id,
                    collection_name=private_name,
                    collection_type=DBDocumentPermissionLevel.PRIVATE.value,
                    is_active=True,
                )
                self.db.add(private_collection)
            else:
                private_name = existing_private.collection_name

            await self._ensure_milvus_collections(public_name, private_name)

            try:
                bucket_name = self._build_bucket_name(tenant_id)
                await minio_service.ensure_bucket(bucket_name)

                public_dir_key = f"{tenant_id}/{department_id}/public/"
                private_dir_key = f"{tenant_id}/{department_id}/private/"

                await minio_service.put_bytes(bucket_name, f"{public_dir_key}.keep", b"", "text/plain")
                await minio_service.put_bytes(bucket_name, f"{private_dir_key}.keep", b"", "text/plain")

                logger.info(f"Created MinIO directories: {public_dir_key}, {private_dir_key}")

            except Exception as e:
                logger.warning(f"Failed to create MinIO directories: {e}")

            return {
                "public_root_id": str(public_root_folder.id),
                "private_root_id": str(private_root_folder.id),
                "public_collection": public_name,
                "private_collection": private_name,
            }
        except Exception as e:
            logger.error(f"Failed to create department root for {department_id}: {e}")
            return None

    # ------------------- Folder Management -------------------

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
            if not access_level:
                if parent_folder_id:
                    parent_result = await self.db.execute(
                        select(DocumentFolder).where(DocumentFolder.id == parent_folder_id)
                    )
                    parent_folder: Optional[DocumentFolder] = parent_result.scalar_one_or_none()
                    if not parent_folder:
                        raise ValueError(f"Parent folder {parent_folder_id} not found")

                    if str(parent_folder.department_id) != department_id:
                        raise ValueError("Parent folder belongs to different department")

                    if parent_folder.access_level == DocumentAccessLevel.PRIVATE.value:
                        access_level = DocumentAccessLevel.PRIVATE
                    else:
                        access_level = DocumentAccessLevel.PUBLIC
                else:
                    access_level = DocumentAccessLevel.PUBLIC

            if parent_folder_id:
                parent_result = await self.db.execute(
                    select(DocumentFolder).where(DocumentFolder.id == parent_folder_id)
                )
                parent_folder: Optional[DocumentFolder] = parent_result.scalar_one_or_none()
                if not parent_folder:
                    raise ValueError(f"Parent folder {parent_folder_id} not found")

                if str(parent_folder.department_id) != department_id:
                    raise ValueError("Parent folder belongs to different department")

                folder_path = f"{parent_folder.folder_path.rstrip('/')}/{folder_name}/"
            else:
                folder_path = f"/{folder_name}/"

            existing_result = await self.db.execute(
                select(DocumentFolder).where(
                    and_(
                        DocumentFolder.department_id == department_id,
                        DocumentFolder.folder_path == folder_path
                    )
                )
            )
            if existing_result.scalar_one_or_none():
                raise ValueError(f"Folder with path {folder_path} already exists")

            new_folder = DocumentFolder(
                department_id=department_id,
                folder_name=folder_name,
                folder_path=folder_path,
                parent_folder_id=parent_folder_id,
                access_level=access_level.value,
                created_by=created_by
            )
            
            self.db.add(new_folder)
            await self.db.flush()
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

    async def get_folder_tree(self, department_id: str, folder_id: Optional[str] = None, access_level: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Get folder tree structure starting from folder_id (or root if None) with optional access_level filter"""
        try:
            if folder_id:
                result = await self.db.execute(
                    select(DocumentFolder).where(
                        and_(
                            DocumentFolder.id == folder_id,
                            DocumentFolder.department_id == department_id
                        )
                    )
                )
                root_folder = result.scalar_one_or_none()
                if not root_folder:
                    return None
            else:
                # Build query for root folders
                query = select(DocumentFolder).where(
                    and_(
                        DocumentFolder.department_id == department_id,
                        DocumentFolder.folder_path == DocumentConstants.ROOT_FOLDER_PATH
                    )
                )

                if access_level:
                    query = query.where(DocumentFolder.access_level == access_level)

                result = await self.db.execute(query)
                root_folders = result.scalars().all()

                if not root_folders:
                    return None

                if len(root_folders) == 1:
                    root_folder = root_folders[0]
                else:
                    return await self._build_combined_folder_tree(root_folders)

            async def _build_tree(folder: DocumentFolder) -> Dict[str, Any]:
                subfolders_result = await self.db.execute(
                    select(DocumentFolder).where(
                        DocumentFolder.parent_folder_id == folder.id
                    )
                )
                subfolders = subfolders_result.scalars().all()
                
                documents_result = await self.db.execute(
                    select(Document).where(Document.folder_id == str(folder.id))
                )
                documents = documents_result.scalars().all()
                
                return {
                    "id": str(folder.id),
                    "folder_name": folder.folder_name,
                    "folder_path": folder.folder_path,
                    "access_level": folder.access_level,
                    "document_count": len(documents),
                    "documents": [
                        {
                            "id": str(doc.id),
                            "filename": doc.filename,
                            "title": doc.title,
                            "file_size": doc.file_size,
                            "file_type": doc.file_type,
                            "access_level": doc.access_level,
                            "processing_status": doc.processing_status
                        } for doc in documents
                    ],
                    "subfolders": [await _build_tree(subfolder) for subfolder in subfolders]
                }

            return await _build_tree(root_folder)

        except Exception as e:
            logger.error(f"Failed to get folder tree: {e}")
            return None

    async def _build_combined_folder_tree(self, root_folders: List) -> Dict[str, Any]:
        """Build combined tree structure for multiple root folders"""
        try:
            combined_tree = {
                "id": "combined_root",
                "folder_name": "Department Root",
                "folder_path": "/",
                "access_level": "mixed",
                "subfolders": [],
                "documents": []
            }

            for root_folder in root_folders:
                async def _build_tree(folder: DocumentFolder) -> Dict[str, Any]:
                    subfolders_result = await self.db.execute(
                        select(DocumentFolder).where(
                            DocumentFolder.parent_folder_id == folder.id
                        )
                    )
                    subfolders = subfolders_result.scalars().all()

                    documents_result = await self.db.execute(
                        select(Document).where(Document.folder_id == str(folder.id))
                    )
                    documents = documents_result.scalars().all()

                    return {
                        "id": str(folder.id),
                        "folder_name": folder.folder_name,
                        "folder_path": folder.folder_path,
                        "access_level": folder.access_level,
                        "document_count": len(documents),
                        "documents": [
                            {
                                "id": str(doc.id),
                                "filename": doc.filename,
                                "title": doc.title,
                                "file_size": doc.file_size,
                                "file_type": doc.file_type,
                                "access_level": doc.access_level,
                                "processing_status": doc.processing_status
                            } for doc in documents
                        ],
                        "subfolders": [await _build_tree(subfolder) for subfolder in subfolders]
                    }

                root_tree = await _build_tree(root_folder)
                combined_tree["subfolders"].append(root_tree)

            return combined_tree

        except Exception as e:
            logger.error(f"Failed to build combined folder tree: {e}")
            return {
                "id": "error",
                "folder_name": "Error",
                "folder_path": "/",
                "access_level": "error",
                "subfolders": [],
                "documents": []
            }

    # ------------------- Helper methods -------------------

    def _build_bucket_name(self, tenant_id: str) -> str:
        """Build bucket name from tenant ID using settings"""
        return DocumentConstants.BUCKET_NAME_TEMPLATE.format(
            prefix=settings.storage.bucket_prefix,
            tenant_id=tenant_id
        )

    async def _build_folder_path_recursive(self, folder_id: Optional[str]) -> str:
        """
        Build recursive folder path from folder UUID chain.
        Returns path like: uuid1/uuid2/uuid3/ (with trailing slash)
        For root folder (/), returns empty string
        """
        if not folder_id:
            return ""
            
        try:
            result = await self.db.execute(
                select(DocumentFolder).where(DocumentFolder.id == folder_id)
            )
            folder: Optional[DocumentFolder] = result.scalar_one_or_none()
            
            if not folder:
                return ""
                
            if folder.folder_path == DocumentConstants.ROOT_FOLDER_PATH:
                return ""
                
            path_parts = []
            current_folder = folder
            
            while current_folder and current_folder.folder_path != DocumentConstants.ROOT_FOLDER_PATH:
                path_parts.append(str(current_folder.id))
                
                if current_folder.parent_folder_id:
                    result = await self.db.execute(
                        select(DocumentFolder).where(DocumentFolder.id == current_folder.parent_folder_id)
                    )
                    current_folder = result.scalar_one_or_none()
                else:
                    break
                    
            path_parts.reverse()
            return "/".join(path_parts) + "/" if path_parts else ""
            
        except Exception as e:
            logger.warning(f"Failed to build folder path for {folder_id}: {e}")
            return ""

    def _build_storage_key(self, tenant_id: str, department_id: str, access_level: str, folder_path: str, document_uuid: str, filename: str) -> str:
        """Build storage key for MinIO using document UUID, access level and recursive folder path"""
        return DocumentConstants.STORAGE_KEY_TEMPLATE.format(
            tenant_id=tenant_id,
            department_id=department_id,
            access_level=access_level.lower(),
            folder_path=folder_path,
            document_uuid=document_uuid,
            filename=os.path.basename(filename)
        )

    def _get_access_level_string(self, access_level: DBDocumentPermissionLevel) -> str:
        """Convert DBDocumentPermissionLevel to DocumentAccessLevel string"""
        return (DocumentAccessLevel.PRIVATE.value 
                if access_level == DBDocumentPermissionLevel.PRIVATE 
                else DocumentAccessLevel.PUBLIC.value)

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

    async def _index_to_milvus(self, collection_name: str, chunks: List[Any], base_meta: Dict[str, Any], access: DBDocumentPermissionLevel) -> int:
        """Index document chunks to Milvus"""
        try:
            count = await milvus_service.index_document_chunks(
                collection_name=collection_name,
                chunks=chunks,
                metadata=base_meta,
                milvus_instance=access.value,
            )
            return int(count or 0)
        except Exception as e:
            logger.error(f"Milvus indexing failed: {e}")
            raise

    # ------------------- CRUD methods -------------------

    async def upload_document(
        self,
        tenant_id: str,
        department_id: str,
        uploaded_by: str,
        file_name: str,
        file_bytes: bytes,
        file_mime_type: str,
        access_level: DBDocumentPermissionLevel,
        collection_name: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Optional[DocumentUploadResult]:
        """
        Transactional upload: MinIO -> DB -> Milvus. If any step fails, rollback MinIO + DB.
        Progress is published to Kafka.
        """
        bucket = self._build_bucket_name(tenant_id)
        doc: Optional[Document] = None
        storage_key: Optional[str] = None
        
        try:
            await self._publish_progress(
                tenant_id, department_id, None, 
                DocumentConstants.PROGRESS_START, 
                KafkaMessageStatus.PROCESSING, 
                "Starting upload"
            )
            
            result = await self.db.execute(
                select(DocumentCollection).where(DocumentCollection.collection_name == collection_name)
            )
            collection: Optional[DocumentCollection] = result.scalar_one_or_none()
            if not collection:
                raise ValueError(f"Collection {collection_name} not found")

            access_level_string = self._get_access_level_string(access_level)
            result = await self.db.execute(
                select(DocumentFolder).where(
                    and_(
                        DocumentFolder.department_id == department_id,
                        DocumentFolder.folder_path == DocumentConstants.ROOT_FOLDER_PATH,
                        DocumentFolder.access_level == access_level_string
                    )
                )
            )
            root_folder: Optional[DocumentFolder] = result.scalar_one_or_none()

            title = os.path.splitext(os.path.basename(file_name))[0]
            doc = Document(
                filename=file_name,
                title=title,
                description=metadata.get("description") if metadata else None,
                department_id=department_id,
                folder_id=str(root_folder.id) if root_folder else None,
                collection_id=str(collection.id),
                uploaded_by=uploaded_by,
                access_level=self._get_access_level_string(access_level),
                file_size=len(file_bytes),
                file_type=file_mime_type,
                storage_key="",  
                bucket_name=bucket,
                processing_status=DocumentProcessingStatus.PROCESSING.value,
                vector_status=VectorProcessingStatus.PENDING.value,
                metadata=metadata or {},
            )
            self.db.add(doc)
            await self.db.flush()
            
            folder_path = await self._build_folder_path_recursive(str(root_folder.id) if root_folder else None)
            storage_key = self._build_storage_key(tenant_id, department_id, access_level_string, folder_path, str(doc.id), file_name)
            doc.storage_key = storage_key
            await self.db.flush()
            
            await self._publish_progress(
                tenant_id, department_id, str(doc.id), 
                DocumentConstants.PROGRESS_DB_CREATED, 
                KafkaMessageStatus.PROCESSING, 
                "Created DB record"
            )
            
            await minio_service.ensure_bucket(bucket)
            await minio_service.put_bytes(bucket, storage_key, file_bytes, file_mime_type)
            await self._publish_progress(
                tenant_id, department_id, str(doc.id), 
                DocumentConstants.PROGRESS_STORAGE_UPLOADED, 
                KafkaMessageStatus.PROCESSING, 
                "Uploaded to storage"
            )

            with tempfile.TemporaryDirectory() as tmpdir:
                tmp_path = os.path.join(tmpdir, os.path.basename(file_name))
                with open(tmp_path, "wb") as f:
                    f.write(file_bytes)
                chunks = await self.file_processor.process_file(
                    file_path=tmp_path,
                    file_name=file_name,
                    doc_id=str(doc.id),
                    metadata={"department_id": department_id, "collection_name": collection_name}
                )
            await self._publish_progress(
                tenant_id, department_id, str(doc.id), 
                DocumentConstants.PROGRESS_CHUNKS_EXTRACTED, 
                KafkaMessageStatus.PROCESSING, 
                "Extracted chunks"
            )

            base_meta = {"document_id": str(doc.id), "department_id": department_id}
            indexed = await self._index_to_milvus(collection_name, chunks, base_meta, access_level)

            doc.processing_status = DocumentProcessingStatus.COMPLETED.value
            doc.vector_status = VectorProcessingStatus.COMPLETED.value
            doc.chunk_count = int(indexed)
            await self.db.flush()
            await self.db.commit()

            await self._publish_progress(
                tenant_id, department_id, str(doc.id), 
                DocumentConstants.PROGRESS_COMPLETED, 
                KafkaMessageStatus.COMPLETED, 
                "Ingestion completed",
                {"chunks": indexed}
            )

            return DocumentUploadResult(
                document_id=str(doc.id),
                file_name=file_name,
                bucket=bucket,
                storage_key=storage_key,
                chunks=indexed,
                status=DocumentProcessingStatus.COMPLETED.value,
            )
            
        except Exception as e:
            logger.error(f"Upload failed: {e}")
            await self.db.rollback()
            
            if storage_key:
                try:
                    await minio_service.delete_object(bucket, storage_key)
                except Exception:
                    pass
                    
            await self._publish_progress(
                tenant_id, department_id, str(doc.id) if doc else None, 
                DocumentConstants.PROGRESS_COMPLETED, 
                KafkaMessageStatus.FAILED, 
                str(e)
            )
            return DocumentUploadResult(error=str(e))

    async def upload_document_to_folder(
        self,
        tenant_id: str,
        department_id: str,
        folder_id: str,
        uploaded_by: str,
        file_name: str,
        file_bytes: bytes,
        file_mime_type: str,
        access_level: DBDocumentPermissionLevel,
        collection_name: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Optional[DocumentUploadResult]:
        """
        Upload document to specific folder (not just root).
        Transactional upload: MinIO -> DB -> Milvus. If any step fails, rollback MinIO + DB.
        Progress is published to Kafka.
        """
        bucket = self._build_bucket_name(tenant_id)
        doc: Optional[Document] = None
        storage_key: Optional[str] = None
        
        try:
            await self._publish_progress(
                tenant_id, department_id, None, 
                DocumentConstants.PROGRESS_START, 
                KafkaMessageStatus.PROCESSING, 
                "Starting upload"
            )
            
            result = await self.db.execute(
                select(DocumentFolder).where(
                    and_(
                        DocumentFolder.id == folder_id,
                        DocumentFolder.department_id == department_id
                    )
                )
            )
            target_folder: Optional[DocumentFolder] = result.scalar_one_or_none()
            if not target_folder:
                raise ValueError(f"Folder {folder_id} not found in department {department_id}")
            
            result = await self.db.execute(
                select(DocumentCollection).where(DocumentCollection.collection_name == collection_name)
            )
            collection: Optional[DocumentCollection] = result.scalar_one_or_none()
            if not collection:
                raise ValueError(f"Collection {collection_name} not found")

            title = os.path.splitext(os.path.basename(file_name))[0]
            doc = Document(
                filename=file_name,
                title=title,
                description=metadata.get("description") if metadata else None,
                department_id=department_id,
                folder_id=folder_id,
                collection_id=str(collection.id),
                uploaded_by=uploaded_by,
                access_level=self._get_access_level_string(access_level),
                file_size=len(file_bytes),
                file_type=file_mime_type,
                storage_key="",  
                bucket_name=bucket,
                processing_status=DocumentProcessingStatus.PROCESSING.value,
                vector_status=VectorProcessingStatus.PENDING.value,
                metadata=metadata or {},
            )
            self.db.add(doc)
            await self.db.flush()
            
            folder_path = await self._build_folder_path_recursive(folder_id)
            storage_key = self._build_storage_key(tenant_id, department_id, access_level_string, folder_path, str(doc.id), file_name)
            doc.storage_key = storage_key
            await self.db.flush()
            
            await self._publish_progress(
                tenant_id, department_id, str(doc.id), 
                DocumentConstants.PROGRESS_DB_CREATED, 
                KafkaMessageStatus.PROCESSING, 
                "Created DB record"
            )
            
            await minio_service.ensure_bucket(bucket)
            await minio_service.put_bytes(bucket, storage_key, file_bytes, file_mime_type)
            await self._publish_progress(
                tenant_id, department_id, str(doc.id), 
                DocumentConstants.PROGRESS_STORAGE_UPLOADED, 
                KafkaMessageStatus.PROCESSING, 
                "Uploaded to storage"
            )

            with tempfile.TemporaryDirectory() as tmpdir:
                tmp_path = os.path.join(tmpdir, os.path.basename(file_name))
                with open(tmp_path, "wb") as f:
                    f.write(file_bytes)
                chunks = await self.file_processor.process_file(
                    file_path=tmp_path,
                    file_name=file_name,
                    doc_id=str(doc.id),
                    metadata={"department_id": department_id, "collection_name": collection_name}
                )
            await self._publish_progress(
                tenant_id, department_id, str(doc.id), 
                DocumentConstants.PROGRESS_CHUNKS_EXTRACTED, 
                KafkaMessageStatus.PROCESSING, 
                "Extracted chunks"
            )

            base_meta = {"document_id": str(doc.id), "department_id": department_id}
            indexed = await self._index_to_milvus(collection_name, chunks, base_meta, access_level)

            doc.processing_status = DocumentProcessingStatus.COMPLETED.value
            doc.vector_status = VectorProcessingStatus.COMPLETED.value
            doc.chunk_count = int(indexed)
            await self.db.flush()
            await self.db.commit()

            await self._publish_progress(
                tenant_id, department_id, str(doc.id), 
                DocumentConstants.PROGRESS_COMPLETED, 
                KafkaMessageStatus.COMPLETED, 
                "Ingestion completed",
                {"chunks": indexed, "folder_path": folder_path}
            )

            return DocumentUploadResult(
                document_id=str(doc.id),
                file_name=file_name,
                bucket=bucket,
                storage_key=storage_key,
                chunks=indexed,
                status=DocumentProcessingStatus.COMPLETED.value,
            )
            
        except Exception as e:
            logger.error(f"Upload to folder failed: {e}")
            await self.db.rollback()
            
            if storage_key:
                try:
                    await minio_service.delete_object(bucket, storage_key)
                except Exception:
                    pass
                    
            await self._publish_progress(
                tenant_id, department_id, str(doc.id) if doc else None, 
                DocumentConstants.PROGRESS_COMPLETED, 
                KafkaMessageStatus.FAILED, 
                str(e)
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
        base_metadata: Optional[Dict[str, Any]] = None
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

    async def update_document_info(
        self,
        document_id: str,
        title: Optional[str] = None,
        description: Optional[str] = None,
        access_level: Optional[DBDocumentPermissionLevel] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """Update document basic information (DB only)."""
        try:
            result = await self.db.execute(select(Document).where(Document.id == document_id))
            doc: Optional[Document] = result.scalar_one_or_none()
            if not doc:
                return False
            if title is not None:
                doc.title = title
            if description is not None:
                doc.description = description
            if access_level is not None:
                doc.access_level = self._get_access_level_string(access_level)
            if metadata is not None:
                doc.metadata = metadata
            await self.db.flush()
            await self.db.commit()
            return True
        except Exception as e:
            logger.error(f"Update document info failed: {e}")
            await self.db.rollback()
            return False 