"""
MinIO Service for object storage operations
Handles file upload, download, delete with async wrapper
"""
from typing import Optional, List, Dict, Any, BinaryIO
import asyncio
from io import BytesIO
from utils.logging import get_logger
from config.settings import get_settings

logger = get_logger(__name__)
settings = get_settings()

try:
    from minio import Minio
    from minio.error import S3Error, InvalidResponseError
    MINIO_AVAILABLE = True
except ImportError:
    MINIO_AVAILABLE = False
    logger.warning("minio package not available - MinIO functionality disabled")


class MinioService:
    """
    MinIO service for object storage operations with async wrapper
    """
    
    def __init__(self):
        self._client: Optional[Minio] = None
        self._initialized = False
        
        if not MINIO_AVAILABLE:
            logger.warning("MinIO service initialized but minio package not available")
            return
            
        # Get settings from config
        self._endpoint = settings.storage.endpoint
        self._access_key = settings.storage.access_key
        self._secret_key = settings.storage.secret_key
        self._secure = settings.storage.secure
        
        self._initialize_client()
    
    def _initialize_client(self) -> None:
        """Initialize MinIO client"""
        if not MINIO_AVAILABLE:
            return
            
        try:
            self._client = Minio(
                endpoint=self._endpoint,
                access_key=self._access_key,
                secret_key=self._secret_key,
                secure=self._secure
            )
            self._initialized = True
            logger.info(f"MinIO client initialized - endpoint: {self._endpoint}, secure: {self._secure}")
            
        except Exception as e:
            logger.error(f"Failed to initialize MinIO client: {e}")
            self._client = None
            raise
    
    def _check_client(self) -> None:
        """Check if MinIO client is available"""
        if not MINIO_AVAILABLE:
            raise RuntimeError("MinIO package not available")
        if not self._initialized or not self._client:
            raise RuntimeError("MinIO client not initialized")
    
    async def ensure_bucket(self, bucket_name: str) -> None:
        """Ensure bucket exists, create if not"""
        self._check_client()
        
        def _ensure_bucket():
            try:
                if not self._client.bucket_exists(bucket_name):
                    self._client.make_bucket(bucket_name)
                    logger.info(f"Created MinIO bucket: {bucket_name}")
                else:
                    logger.debug(f"MinIO bucket already exists: {bucket_name}")
            except S3Error as e:
                logger.error(f"Error ensuring bucket {bucket_name}: {e}")
                raise
        
        await asyncio.to_thread(_ensure_bucket)
    
    async def put_object(
        self, 
        bucket_name: str, 
        object_name: str, 
        data: BinaryIO, 
        length: int,
        content_type: str = "application/octet-stream",
        metadata: Optional[Dict[str, str]] = None
    ) -> None:
        """Upload object to MinIO"""
        self._check_client()
        
        def _put_object():
            try:
                self._client.put_object(
                    bucket_name=bucket_name,
                    object_name=object_name,
                    data=data,
                    length=length,
                    content_type=content_type,
                    metadata=metadata
                )
                logger.debug(f"Uploaded object: {bucket_name}/{object_name}")
            except S3Error as e:
                logger.error(f"Error uploading object {bucket_name}/{object_name}: {e}")
                raise
        
        await asyncio.to_thread(_put_object)
    
    async def put_bytes(
        self,
        bucket_name: str,
        object_name: str,
        data: bytes,
        content_type: str = "application/octet-stream",
        metadata: Optional[Dict[str, str]] = None
    ) -> None:
        """Upload bytes to MinIO"""
        bio = BytesIO(data)
        await self.put_object(
            bucket_name=bucket_name,
            object_name=object_name,
            data=bio,
            length=len(data),
            content_type=content_type,
            metadata=metadata
        )
    
    async def get_object(self, bucket_name: str, object_name: str) -> BinaryIO:
        """Download object from MinIO"""
        self._check_client()
        
        def _get_object():
            try:
                response = self._client.get_object(bucket_name, object_name)
                return response
            except S3Error as e:
                logger.error(f"Error downloading object {bucket_name}/{object_name}: {e}")
                raise
        
        return await asyncio.to_thread(_get_object)
    
    async def get_bytes(self, bucket_name: str, object_name: str) -> bytes:
        """Download object as bytes from MinIO"""
        obj = await self.get_object(bucket_name, object_name)
        try:
            return obj.read()
        finally:
            obj.close()
            obj.release_conn()
    
    async def delete_object(self, bucket_name: str, object_name: str) -> None:
        """Delete object from MinIO"""
        self._check_client()
        
        def _delete_object():
            try:
                self._client.remove_object(bucket_name, object_name)
                logger.debug(f"Deleted object: {bucket_name}/{object_name}")
            except S3Error as e:
                logger.error(f"Error deleting object {bucket_name}/{object_name}: {e}")
                raise
        
        await asyncio.to_thread(_delete_object)
    
    async def list_objects(
        self, 
        bucket_name: str, 
        prefix: Optional[str] = None,
        recursive: bool = False
    ) -> List[Dict[str, Any]]:
        """List objects in bucket"""
        self._check_client()
        
        def _list_objects():
            try:
                objects = []
                for obj in self._client.list_objects(bucket_name, prefix=prefix, recursive=recursive):
                    objects.append({
                        "name": obj.object_name,
                        "size": obj.size,
                        "etag": obj.etag,
                        "last_modified": obj.last_modified.isoformat() if obj.last_modified else None,
                        "content_type": obj.content_type,
                        "is_dir": obj.is_dir
                    })
                return objects
            except S3Error as e:
                logger.error(f"Error listing objects in {bucket_name}: {e}")
                raise
        
        return await asyncio.to_thread(_list_objects)
    
    async def object_exists(self, bucket_name: str, object_name: str) -> bool:
        """Check if object exists"""
        self._check_client()
        
        def _object_exists():
            try:
                self._client.stat_object(bucket_name, object_name)
                return True
            except S3Error:
                return False
        
        return await asyncio.to_thread(_object_exists)
    
    async def get_object_info(self, bucket_name: str, object_name: str) -> Optional[Dict[str, Any]]:
        """Get object metadata"""
        self._check_client()
        
        def _get_object_info():
            try:
                stat = self._client.stat_object(bucket_name, object_name)
                return {
                    "name": object_name,
                    "size": stat.size,
                    "etag": stat.etag,
                    "last_modified": stat.last_modified.isoformat() if stat.last_modified else None,
                    "content_type": stat.content_type,
                    "metadata": dict(stat.metadata) if stat.metadata else {}
                }
            except S3Error as e:
                logger.error(f"Error getting object info {bucket_name}/{object_name}: {e}")
                return None
        
        return await asyncio.to_thread(_get_object_info)
    
    async def copy_object(
        self,
        source_bucket: str,
        source_object: str,
        dest_bucket: str,
        dest_object: str
    ) -> None:
        """Copy object within MinIO"""
        self._check_client()
        
        def _copy_object():
            try:
                from minio.commonconfig import CopySource
                copy_source = CopySource(source_bucket, source_object)
                self._client.copy_object(dest_bucket, dest_object, copy_source)
                logger.debug(f"Copied object: {source_bucket}/{source_object} -> {dest_bucket}/{dest_object}")
            except S3Error as e:
                logger.error(f"Error copying object: {e}")
                raise
        
        await asyncio.to_thread(_copy_object)
    
    async def generate_presigned_url(
        self,
        bucket_name: str,
        object_name: str,
        expires_in_seconds: int = 3600,
        method: str = "GET"
    ) -> str:
        """Generate presigned URL for object access"""
        self._check_client()
        
        def _generate_url():
            try:
                from datetime import timedelta
                if method.upper() == "GET":
                    url = self._client.presigned_get_object(
                        bucket_name, 
                        object_name, 
                        expires=timedelta(seconds=expires_in_seconds)
                    )
                elif method.upper() == "PUT":
                    url = self._client.presigned_put_object(
                        bucket_name, 
                        object_name, 
                        expires=timedelta(seconds=expires_in_seconds)
                    )
                else:
                    raise ValueError(f"Unsupported method: {method}")
                return url
            except S3Error as e:
                logger.error(f"Error generating presigned URL: {e}")
                raise
        
        return await asyncio.to_thread(_generate_url)
    
    async def health_check(self) -> Dict[str, Any]:
        """Check MinIO service health"""
        health = {
            "minio_available": MINIO_AVAILABLE,
            "client_initialized": self._initialized,
            "endpoint": self._endpoint if self._initialized else None,
            "secure": self._secure if self._initialized else None
        }
        
        if self._initialized and self._client:
            try:
                # Try to list buckets as health check
                def _health_check():
                    buckets = self._client.list_buckets()
                    return len(buckets)
                
                bucket_count = await asyncio.to_thread(_health_check)
                health["status"] = "healthy"
                health["bucket_count"] = bucket_count
            except Exception as e:
                health["status"] = "unhealthy"
                health["error"] = str(e)
        else:
            health["status"] = "not_initialized"
        
        return health


# Global MinIO service instance
minio_service = MinioService()

  