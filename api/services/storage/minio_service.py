import asyncio
import io
import os
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple, Union, BinaryIO
from pathlib import Path
import hashlib
import json

from minio import Minio
from minio.error import S3Error, InvalidResponseError
from minio.commonconfig import REPLACE, CopySource
from minio.deleteobjects import DeleteObject

from config.settings import get_settings
from utils.logging import get_logger
from core.exceptions import StorageError
from common.types import Department, FileType
from utils.datetime_utils import CustomDateTime

logger = get_logger(__name__)


class MinioService:
    """
    Service quản lý object storage sử dụng MinIO
    Hỗ trợ upload, download, delete documents và metadata management
    """

    def __init__(self):
        self.settings = get_settings()
        self.client: Optional[Minio] = None
        self.bucket_prefix = self.settings.storage.bucket_prefix
        self._initialized = False
        
        # Department bucket mapping
        self.department_buckets = {
            Department.HR: f"{self.bucket_prefix}-hr-documents",
            Department.IT: f"{self.bucket_prefix}-it-documents", 
            Department.FINANCE: f"{self.bucket_prefix}-finance-documents",
            Department.ADMIN: f"{self.bucket_prefix}-admin-documents",
            Department.GENERAL: f"{self.bucket_prefix}-general-documents"
        }
        
        # Backup và versioning buckets
        self.backup_bucket = f"{self.bucket_prefix}-backups"
        self.metadata_bucket = f"{self.bucket_prefix}-metadata"

    async def initialize(self):
        """Initialize MinIO client và create buckets"""
        try:
            storage_config = self.settings.storage
            self.client = Minio(
                endpoint=storage_config.endpoint,
                access_key=storage_config.access_key,
                secret_key=storage_config.secret_key,
                secure=storage_config.secure
            )
            
            await self._create_buckets()
            
            self._initialized = True
            logger.info("MinIO service initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize MinIO service: {e}")
            raise StorageError(f"MinIO initialization failed: {e}")

    async def _create_buckets(self):
        """Create all required buckets"""
        buckets_to_create = list(self.department_buckets.values())
        buckets_to_create.extend([self.backup_bucket, self.metadata_bucket])
        
        for bucket_name in buckets_to_create:
            try:
                if not self.client.bucket_exists(bucket_name):
                    self.client.make_bucket(bucket_name)
                    logger.info(f"Created bucket: {bucket_name}")
                else:
                    logger.debug(f"Bucket already exists: {bucket_name}")
            except Exception as e:
                logger.error(f"Failed to create bucket {bucket_name}: {e}")
                raise

    def _get_bucket_name(self, department: Department) -> str:
        """Get bucket name cho department"""
        return self.department_buckets.get(department, self.department_buckets[Department.GENERAL])

    def _generate_object_key(
        self, 
        document_id: str, 
        filename: str, 
        department: Department,
        version: Optional[str] = None
    ) -> str:
        """Generate object key cho document"""
        # Department/year/month/document_id/filename
        now = CustomDateTime.now()
        base_path = f"{department.value}/{now.year}/{now.month:02d}/{document_id}"
        
        if version:
            return f"{base_path}/v{version}/{filename}"
        else:
            return f"{base_path}/{filename}"

    def _generate_metadata_key(self, document_id: str, department: Department) -> str:
        """Generate metadata key"""
        now = CustomDateTime.now()
        return f"{department.value}/{now.year}/{now.month:02d}/{document_id}/metadata.json"

    async def upload_document(
        self,
        file_content: bytes,
        filename: str,
        document_id: str,
        department: Department,
        metadata: Dict[str, Any],
        file_type: FileType = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Upload document to MinIO
        
        Args:
            file_content: Raw file content
            filename: Original filename
            document_id: Unique document identifier
            department: Document department
            metadata: Document metadata
            file_type: File type enum
            **kwargs: Additional parameters
            
        Returns:
            Dict with upload result and object info
        """
        
        if not self._initialized:
            await self.initialize()
        
        try:
            bucket_name = self._get_bucket_name(department)
            object_key = self._generate_object_key(document_id, filename, department)
            
            # Prepare metadata for MinIO
            object_metadata = {
                "document-id": document_id,
                "department": department.value,
                "original-filename": filename,
                "upload-timestamp": CustomDateTime.now().isoformat(),
                "file-type": file_type.value if file_type else "unknown",
                "content-hash": hashlib.sha256(file_content).hexdigest(),
                "content-size": str(len(file_content))
            }
            
            # Add custom metadata
            for key, value in metadata.items():
                if isinstance(value, (str, int, float)):
                    object_metadata[f"custom-{key}"] = str(value)
            
            # Upload file
            file_stream = io.BytesIO(file_content)
            
            result = self.client.put_object(
                bucket_name=bucket_name,
                object_name=object_key,
                data=file_stream,
                length=len(file_content),
                metadata=object_metadata,
                content_type=self._get_content_type(filename)
            )
            
            # Upload metadata separately 
            metadata_key = self._generate_metadata_key(document_id, department)
            await self._upload_metadata(bucket_name, metadata_key, {
                "document_id": document_id,
                "filename": filename,
                "department": department.value,
                "object_key": object_key,
                "metadata": metadata,
                "upload_info": {
                    "timestamp": CustomDateTime.now().isoformat(),
                    "etag": result.etag,
                    "version_id": result.version_id
                }
            })
            
            logger.info(f"Document uploaded successfully: {object_key}")
            
            return {
                "status": "success",
                "bucket_name": bucket_name,
                "object_key": object_key,
                "metadata_key": metadata_key,
                "etag": result.etag,
                "version_id": result.version_id,
                "content_hash": object_metadata["content-hash"],
                "file_size": len(file_content)
            }
            
        except Exception as e:
            logger.error(f"Failed to upload document {document_id}: {e}")
            raise StorageError(f"Document upload failed: {e}")

    async def download_document(
        self,
        document_id: str,
        department: Department,
        version: Optional[str] = None
    ) -> Tuple[bytes, Dict[str, Any]]:
        """
        Download document from MinIO
        
        Args:
            document_id: Document identifier
            department: Document department  
            version: Specific version (optional)
            
        Returns:
            Tuple of (file_content, metadata)
        """
        
        if not self._initialized:
            await self.initialize()
        
        try:
            # Get metadata first để tìm object key
            metadata = await self._get_document_metadata(document_id, department)
            if not metadata:
                raise StorageError(f"Document metadata not found: {document_id}")
            
            bucket_name = self._get_bucket_name(department)
            object_key = metadata.get("object_key")
            
            if version:
                # Construct versioned object key
                filename = metadata.get("filename", "")
                object_key = self._generate_object_key(document_id, filename, department, version)
            
            # Download file
            response = self.client.get_object(bucket_name, object_key)
            file_content = response.read()
            
            # Get object metadata
            stat = self.client.stat_object(bucket_name, object_key)
            object_metadata = stat.metadata or {}
            
            logger.info(f"Document downloaded successfully: {object_key}")
            
            return file_content, {
                "document_id": document_id,
                "bucket_name": bucket_name,
                "object_key": object_key,
                "file_size": stat.size,
                "last_modified": stat.last_modified,
                "etag": stat.etag,
                "content_type": stat.content_type,
                "metadata": object_metadata,
                "custom_metadata": metadata
            }
            
        except S3Error as e:
            if e.code == "NoSuchKey":
                raise StorageError(f"Document not found: {document_id}")
            else:
                logger.error(f"S3 error downloading document {document_id}: {e}")
                raise StorageError(f"Download failed: {e}")
        except Exception as e:
            logger.error(f"Failed to download document {document_id}: {e}")
            raise StorageError(f"Document download failed: {e}")

    async def delete_document(
        self,
        document_id: str,
        department: Department,
        create_backup: bool = True
    ) -> Dict[str, Any]:
        """
        Delete document from MinIO
        
        Args:
            document_id: Document identifier
            department: Document department
            create_backup: Whether to create backup before deletion
            
        Returns:
            Dict with deletion result
        """
        
        if not self._initialized:
            await self.initialize()
        
        try:
            if create_backup:
                await self._backup_document(document_id, department)
            
            # Get metadata để tìm object key
            metadata = await self._get_document_metadata(document_id, department)
            if not metadata:
                logger.warning(f"Document metadata not found for deletion: {document_id}")
                return {"status": "not_found", "document_id": document_id}
            
            bucket_name = self._get_bucket_name(department)
            object_key = metadata.get("object_key")
            metadata_key = self._generate_metadata_key(document_id, department)
            
            # Delete main document
            self.client.remove_object(bucket_name, object_key)
            
            # Delete metadata
            try:
                self.client.remove_object(self.metadata_bucket, metadata_key)
            except S3Error as e:
                logger.warning(f"Failed to delete metadata for {document_id}: {e}")
            
            logger.info(f"Document deleted successfully: {document_id}")
            
            return {
                "status": "success",
                "document_id": document_id,
                "bucket_name": bucket_name,
                "object_key": object_key,
                "backup_created": create_backup
            }
            
        except Exception as e:
            logger.error(f"Failed to delete document {document_id}: {e}")
            raise StorageError(f"Document deletion failed: {e}")

    async def _backup_document(self, document_id: str, department: Department):
        """Create backup của document before deletion"""
        try:
            # Download document
            file_content, metadata = await self.download_document(document_id, department)
            
            # Upload to backup bucket
            timestamp = CustomDateTime.now().strftime("%Y%m%d_%H%M%S")
            backup_key = f"deleted/{department.value}/{document_id}_{timestamp}"
            
            file_stream = io.BytesIO(file_content)
            
            self.client.put_object(
                bucket_name=self.backup_bucket,
                object_name=backup_key,
                data=file_stream,
                length=len(file_content),
                metadata={
                    "original-document-id": document_id,
                    "original-department": department.value,
                    "backup-timestamp": timestamp,
                    "deletion-reason": "user_requested"
                }
            )
            
            logger.info(f"Backup created for document {document_id}: {backup_key}")
            
        except Exception as e:
            logger.error(f"Failed to create backup for document {document_id}: {e}")
            # Don't raise exception, backup failure shouldn't prevent deletion

    async def _upload_metadata(self, bucket_name: str, metadata_key: str, metadata: Dict[str, Any]):
        """Upload metadata to metadata bucket"""
        try:
            metadata_json = json.dumps(metadata, indent=2, default=str)
            metadata_stream = io.BytesIO(metadata_json.encode('utf-8'))
            
            self.client.put_object(
                bucket_name=self.metadata_bucket,
                object_name=metadata_key,
                data=metadata_stream,
                length=len(metadata_json),
                content_type="application/json"
            )
            
        except Exception as e:
            logger.error(f"Failed to upload metadata {metadata_key}: {e}")
            raise

    async def _get_document_metadata(self, document_id: str, department: Department) -> Optional[Dict[str, Any]]:
        """Get document metadata from metadata bucket"""
        try:
            metadata_key = self._generate_metadata_key(document_id, department)
            
            response = self.client.get_object(self.metadata_bucket, metadata_key)
            metadata_json = response.read().decode('utf-8')
            
            return json.loads(metadata_json)
            
        except S3Error as e:
            if e.code == "NoSuchKey":
                return None
            else:
                logger.error(f"Error getting metadata for {document_id}: {e}")
                return None
        except Exception as e:
            logger.error(f"Failed to get metadata for {document_id}: {e}")
            return None

    def _get_content_type(self, filename: str) -> str:
        """Get content type from filename"""
        extension = Path(filename).suffix.lower()
        
        content_types = {
            '.pdf': 'application/pdf',
            '.docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            '.doc': 'application/msword',
            '.xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            '.xls': 'application/vnd.ms-excel',
            '.pptx': 'application/vnd.openxmlformats-officedocument.presentationml.presentation',
            '.ppt': 'application/vnd.ms-powerpoint',
            '.txt': 'text/plain',
            '.html': 'text/html',
            '.htm': 'text/html',
            '.md': 'text/markdown',
            '.json': 'application/json',
            '.xml': 'application/xml',
            '.csv': 'text/csv'
        }
        
        return content_types.get(extension, 'application/octet-stream')

    async def list_documents(
        self,
        department: Optional[Department] = None,
        prefix: Optional[str] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """List documents trong bucket"""
        
        if not self._initialized:
            await self.initialize()
        
        try:
            documents = []
            
            if department:
                buckets = [self._get_bucket_name(department)]
            else:
                buckets = list(self.department_buckets.values())
            
            for bucket_name in buckets:
                objects = self.client.list_objects(
                    bucket_name, 
                    prefix=prefix,
                    recursive=True
                )
                
                count = 0
                for obj in objects:
                    if count >= limit:
                        break
                    
                    documents.append({
                        "bucket_name": bucket_name,
                        "object_key": obj.object_name,
                        "size": obj.size,
                        "last_modified": obj.last_modified,
                        "etag": obj.etag
                    })
                    count += 1
            
            return documents
            
        except Exception as e:
            logger.error(f"Failed to list documents: {e}")
            raise StorageError(f"Document listing failed: {e}")

    async def get_storage_stats(self) -> Dict[str, Any]:
        """Get storage statistics"""
        
        if not self._initialized:
            await self.initialize()
        
        try:
            stats = {
                "buckets": {},
                "total_objects": 0,
                "total_size": 0
            }
            
            for dept, bucket_name in self.department_buckets.items():
                try:
                    objects = list(self.client.list_objects(bucket_name, recursive=True))
                    bucket_size = sum(obj.size for obj in objects)
                    
                    stats["buckets"][dept.value] = {
                        "bucket_name": bucket_name,
                        "object_count": len(objects),
                        "total_size": bucket_size
                    }
                    
                    stats["total_objects"] += len(objects)
                    stats["total_size"] += bucket_size
                    
                except Exception as e:
                    logger.warning(f"Failed to get stats for bucket {bucket_name}: {e}")
                    stats["buckets"][dept.value] = {
                        "bucket_name": bucket_name,
                        "object_count": 0,
                        "total_size": 0,
                        "error": str(e)
                    }
            
            return stats
            
        except Exception as e:
            logger.error(f"Failed to get storage stats: {e}")
            raise StorageError(f"Storage stats failed: {e}")

    async def health_check(self) -> bool:
        """Check MinIO service health"""
        try:
            if not self._initialized:
                return False
            
            # Try to list a bucket to test connectivity
            bucket_name = list(self.department_buckets.values())[0]
            list(self.client.list_objects(bucket_name, max_keys=1))
            
            return True
            
        except Exception as e:
            logger.error(f"MinIO health check failed: {e}")
            return False


# Global instance
minio_service = MinioService()
