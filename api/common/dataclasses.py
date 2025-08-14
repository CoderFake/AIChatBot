from dataclasses import dataclass, field
from typing import Any, Dict, Optional, List
from utils.datetime_utils import DateTimeManager
from datetime import datetime
from common.types import ConfigChangeType, ConfigScope


@dataclass
class ConfigChange:
    """Configuration change event"""
    change_type: ConfigChangeType
    component_name: str
    old_value: Any
    new_value: Any
    user_id: Optional[str] = None
    timestamp: datetime = field(default_factory=DateTimeManager.system_now)
    metadata: Dict[str, Any] = field(default_factory=dict)
    scope: ConfigScope = ConfigScope.SYSTEM
    requires_restart: bool = False
    rollback_data: Optional[Dict[str, Any]] = None


@dataclass 
class ConfigPermission:
    """User configuration permission"""
    user_id: str
    role: str
    department: str
    can_manage_all_tools: bool = False
    can_manage_all_providers: bool = False
    can_manage_all_configs: bool = False
    can_manage_department_tools: bool = False
    can_manage_department_providers: bool = False
    allowed_tools: List[str] = field(default_factory=list)
    allowed_providers: List[str] = field(default_factory=list)
    restrictions: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ConfigValidationResult:
    """Result of configuration validation"""
    is_valid: bool
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    suggestions: List[str] = field(default_factory=list)


@dataclass
class ConfigBackup:
    backup_id: str
    created_at: datetime
    created_by: str
    config_data: Dict[str, Any]
    backup_type: str = "manual" 
    description: Optional[str] = None


@dataclass
class ChatMetadata:
   agent_used: List[str] = field(default_factory=list)
   tools_used: List[str] = field(default_factory=list)
   sources: List[str] = field(default_factory=list)
   confidence_score: float = 0.0
   processing_time: float = 0.0
   follow_up_questions: List[str] = field(default_factory=list)
   token_count: int = 0
   language: str = "vi"


@dataclass
class ChatMessageRole:
   user: str = "user"
   assistant: str = "assistant"
   system: str = "system"


@dataclass
class DocumentUploadRequest:
    """Document upload request data"""
    tenant_id: str
    department_id: str
    uploaded_by: str
    file_name: str
    file_bytes: bytes
    file_mime_type: str
    access_level: str  # Use enum value
    collection_name: str
    metadata: Optional[Dict[str, Any]] = None


@dataclass
class DocumentUploadResult:
    """Document upload result data"""
    document_id: Optional[str] = None
    file_name: Optional[str] = None
    bucket: Optional[str] = None
    storage_key: Optional[str] = None
    chunks: int = 0
    status: str = "failed"
    error: Optional[str] = None


@dataclass
class DocumentProgressEvent:
    """Document processing progress event for Kafka"""
    tenant_id: str
    department_id: str
    document_id: Optional[str]
    progress: int  # 0-100
    status: str  # processing|completed|failed|completed_with_errors
    message: str
    timestamp: datetime = field(default_factory=DateTimeManager.maintainer_now)
    extra: Optional[Dict[str, Any]] = None


@dataclass
class BatchUploadProgress:
    """Batch upload progress tracking"""
    batch_id: str
    tenant_id: str
    department_id: str
    total_files: int
    completed_files: int = 0
    failed_files: int = 0
    status: str = "processing"
    started_at: datetime = field(default_factory=DateTimeManager.maintainer_now)
    completed_at: Optional[datetime] = None


@dataclass
class DocumentDeleteResult:
    """Document delete operation result"""
    document_id: str
    deleted: bool
    errors: List[str] = field(default_factory=list)
    error: Optional[str] = None


@dataclass
class MilvusCollectionInfo:
    """Milvus collection information"""
    collection_name: str
    milvus_instance: str  # public_milvus or private_milvus
    department_id: str
    tenant_id: str
    is_active: bool = True
