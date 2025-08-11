import asyncio
import io
import os
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple, Union, BinaryIO
from pathlib import Path
import hashlib
import json
from io import BytesIO

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
    Service for managing object storage using MinIO (S3-compatible)
    - Initialize MinIO client from settings
    - Ensure bucket exists
    - Ensure logical folder (prefix) exists by creating a zero-byte object with trailing '/'
    - Put object helper
    """

    def __init__(self):
        settings = get_settings()
        self.endpoint: str = settings.MINIO_ENDPOINT
        self.access_key: str = settings.MINIO_ACCESS_KEY
        self.secret_key: str = settings.MINIO_SECRET_KEY
        self.secure: bool = settings.MINIO_SECURE
        self.region: Optional[str] = settings.MINIO_REGION

        if not self.access_key or not self.secret_key:
            logger.error("MinIO credentials are missing")
            raise StorageError("MinIO credentials are missing")

        try:
            self.client = Minio(
                endpoint=self.endpoint,
                access_key=self.access_key,
                secret_key=self.secret_key,
                secure=self.secure,
                region=self.region,
            )
            logger.info("Initialized MinIO client")
        except Exception as e:
            logger.error(f"Failed to initialize MinIO client: {e}")
            raise StorageError("Failed to initialize MinIO client") from e

    def ensure_bucket(self, bucket_name: str) -> bool:
        """Create bucket if not exists (idempotent)."""
        try:
            if not self.client.bucket_exists(bucket_name):
                self.client.make_bucket(bucket_name, location=self.region) if self.region else self.client.make_bucket(bucket_name)
                logger.info(f"Bucket created: {bucket_name}")
            else:
                logger.debug(f"Bucket already exists: {bucket_name}")
            return True
        except S3Error as s3e:
            logger.error(f"MinIO S3 error ensuring bucket {bucket_name}: {s3e}")
            return False
        except Exception as e:
            logger.error(f"Failed to ensure bucket {bucket_name}: {e}")
            return False

    def ensure_prefix(self, bucket_name: str, prefix: str) -> bool:
        """
        Ensure a logical folder prefix exists by putting a zero-byte object with suffix '/'.
        Example: ensure_prefix('tenant-bucket', 'document_root_id/')
        """
        try:
            if not prefix.endswith('/'):
                prefix += '/'
            empty = BytesIO(b"")
            self.client.put_object(
                bucket_name=bucket_name,
                object_name=prefix,
                data=empty,
                length=0,
                content_type="application/octet-stream",
            )
            logger.info(f"Ensured prefix {prefix} in bucket {bucket_name}")
            return True
        except S3Error as s3e:
            logger.error(f"MinIO S3 error ensuring prefix {prefix} in {bucket_name}: {s3e}")
            return False
        except Exception as e:
            logger.error(f"Failed to ensure prefix {prefix} in {bucket_name}: {e}")
            return False

    def put_object(
        self,
        bucket_name: str,
        object_name: str,
        data: BinaryIO,
        length: int,
        content_type: Optional[str] = None,
        metadata: Optional[Dict[str, str]] = None,
    ) -> bool:
        """Upload object to MinIO bucket."""
        try:
            if not self.ensure_bucket(bucket_name):
                raise StorageError(f"Bucket unavailable: {bucket_name}")

            self.client.put_object(
                bucket_name=bucket_name,
                object_name=object_name,
                data=data,
                length=length,
                content_type=content_type or "application/octet-stream",
                metadata=metadata,
            )
            logger.info(f"Uploaded object {object_name} to bucket {bucket_name}")
            return True
        except S3Error as s3e:
            logger.error(f"MinIO S3 error putting object {object_name}: {s3e}")
            return False
        except Exception as e:
            logger.error(f"Failed to put object {object_name} to {bucket_name}: {e}")
            return False

  