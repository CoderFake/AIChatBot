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
    Service for managing object storage using MinIO
    Supports document upload, download, and metadata management
    when department is created, it will create a bucket with the name of the department
    when user is created, it will create a bucket with the name of the user
    when user is deleted, it will delete the bucket with the name of the user
    when department is deleted, it will delete the bucket with the name of the department
    when user is updated, it will update the bucket with the name of the user
    when department is updated, it will update the bucket with the name of the department
    """

  