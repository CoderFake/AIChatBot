from typing import Dict, Any, List, Optional, Tuple
from utils.datetime_utils import CustomDatetime as datetime
import asyncio
import math

from pymilvus import (
    connections, Collection, CollectionSchema, FieldSchema, DataType,
    utility, Index, SearchResult
)
from sentence_transformers import SentenceTransformer

from config.settings import get_settings
from utils.logging import get_logger
from core.exceptions import VectorDatabaseError
from services.types import IndexType
from services.dataclasses.milvus import ChunkingConfig, SearchResult
from utils.file_utils import docling_processor
from common.types import Department

logger = get_logger(__name__)

class MilvusService:
    """
    Milvus service
    - Insert document
    - Search document
    - Delete document
    - Reindex after delete
    """
    pass