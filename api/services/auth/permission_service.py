from typing import List, Dict, Any, Optional, Set
from utils.datetime_utils import CustomDateTime as datetime
import asyncio
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_
from sqlalchemy.orm import joinedload

from models.database.user import User
from models.database.permission import (
    Permission,
    UserPermission,
    Group,
    GroupPermission,
    UserGroupMembership
)
from models.database.tool import Tool
from models.database.document import Document
from common.types import UserRole, Department
from config.settings import get_settings
from utils.logging import get_logger
from core.exceptions import PermissionDeniedError, NotFoundError

logger = get_logger(__name__)
settings = get_settings()


class PermissionService:
    """
    Service for permission management
    - Check permission for user
    - Check permission for group
    - Check permission for tool
    - Check permission for crud document
    - Check permission for crud from milvus(private + puplic or public)
    """
    pass