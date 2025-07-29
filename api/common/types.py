"""
Common types và enums cho toàn bộ hệ thống
Single source of truth để tránh duplicate và đảm bảo consistency
"""
from enum import Enum


class AccessLevel(Enum):
    """Enum define access level for document""" 
    PUBLIC = "public"
    PRIVATE = "private"


class DBDocumentPermissionLevel(Enum):
    PUBLIC = "milvus_public"
    PRIVATE = "milvus_private"

class UserRole(Enum):
    """Enum define user roles"""
    MAINTAINER = "MAINTAINER"
    ADMIN = "ADMIN"
    DEPT_ADMIN = "DEPT_ADMIN"
    DEPT_MANAGER = "DEPT_MANAGER"
    USER = "USER"


class ProcessingStatus(Enum):
    """Enum define processing status"""
    PENDING = "pending"
    PROCESSING = "processing"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    PERMISSION_DENIED = "permission_denied"


class QueryType(Enum):
    """Enum define query type"""
    RAG_QUERY = "rag_query"
    CHITCHAT = "chitchat"
    ACTION_REQUEST = "action_request"
    CLARIFICATION = "clarification"


class QueryDomain(Enum):
    """Enum define query domain"""
    HR = "hr"
    IT = "it" 
    FINANCE = "finance"
    GENERAL = "general"
    CROSS_DEPARTMENT = "cross_department"


class Department(Enum):
    """Enum define departments"""
    HR = "hr"
    IT = "it"
    FINANCE = "finance"
    ADMIN = "admin"
    GENERAL = "general"


class Language(Enum):
    """Enum define languages""" 
    VIETNAMESE = "vi"
    ENGLISH = "en"
    JAPANESE = "ja"
    KOREAN = "ko"


class FileType(Enum):
    """Enum define file types"""
    PDF = "pdf"
    DOCX = "docx"
    TXT = "txt"
    MD = "md"
    DOC = "doc"
    XLSX = "xlsx"
    PPTX = "pptx" 


class ConfigScope(str, Enum):
    """Configuration scope levels"""
    SYSTEM = "system"
    DEPARTMENT = "department"
    USER = "user"
    GLOBAL = "global"


class ConfigChangeType(str, Enum):
    """Types of configuration changes"""
    # Provider changes
    PROVIDER_ENABLED = "provider_enabled"
    PROVIDER_DISABLED = "provider_disabled" 
    PROVIDER_MODEL_CHANGED = "provider_model_changed"
    PROVIDER_CONFIG_UPDATED = "provider_config_updated"
    
    # Tool changes
    TOOL_ENABLED = "tool_enabled"
    TOOL_DISABLED = "tool_disabled"
    TOOL_CONFIG_UPDATED = "tool_config_updated"
    TOOL_PERMISSIONS_CHANGED = "tool_permissions_changed"
    
    # Agent changes
    AGENT_ENABLED = "agent_enabled"
    AGENT_DISABLED = "agent_disabled"
    AGENT_CONFIG_UPDATED = "agent_config_updated"
    
    # Workflow changes
    WORKFLOW_CONFIG_UPDATED = "workflow_config_updated"
    WORKFLOW_TIMEOUT_CHANGED = "workflow_timeout_changed"
    
    # System changes
    SYSTEM_RESTART_REQUIRED = "system_restart_required"
    SYSTEM_CONFIG_RELOADED = "system_config_reloaded"


class ConfigOperationType(str, Enum):
    """Config operation types for OTP verification"""
    TOOL_TOGGLE = "tool_toggle"
    PROVIDER_CHANGE = "provider_change"
    CONFIG_UPDATE = "config_update"
    SYSTEM_RESTART = "system_restart"
    PERMISSIONS_CHANGE = "permissions_change"
