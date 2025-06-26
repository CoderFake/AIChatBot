"""
Common types và enums cho toàn bộ hệ thống
Single source of truth để tránh duplicate và đảm bảo consistency
"""
from enum import Enum


class AccessLevel(Enum):
    """Enum định nghĩa các cấp độ truy cập tài liệu"""
    PUBLIC = "public"
    PRIVATE = "private"
    INTERNAL = "internal"
    CONFIDENTIAL = "confidential"
    RESTRICTED = "restricted"


class UserRole(Enum):
    """Enum định nghĩa các vai trò người dùng"""
    EMPLOYEE = "EMPLOYEE"
    MANAGER = "MANAGER"
    DIRECTOR = "DIRECTOR"
    CEO = "CEO"
    ADMIN = "ADMIN"


class ProcessingStatus(Enum):
    """Trạng thái xử lý chung"""
    PENDING = "pending"
    PROCESSING = "processing"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    PERMISSION_DENIED = "permission_denied"


class QueryType(Enum):
    """Loại query trong hệ thống"""
    RAG_QUERY = "rag_query"
    CHITCHAT = "chitchat"
    ACTION_REQUEST = "action_request"
    CLARIFICATION = "clarification"


class QueryDomain(Enum):
    """Domain của query"""
    HR = "hr"
    IT = "it" 
    FINANCE = "finance"
    GENERAL = "general"
    CROSS_DEPARTMENT = "cross_department"


class Department(Enum):
    """Các phòng ban trong công ty"""
    HR = "hr"
    IT = "it"
    FINANCE = "finance"
    ADMIN = "admin"
    GENERAL = "general"


class Language(Enum):
    """Ngôn ngữ hỗ trợ"""
    VIETNAMESE = "vi"
    ENGLISH = "en"
    JAPANESE = "ja"
    KOREAN = "ko"


class FileType(Enum):
    """Loại file hỗ trợ"""
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
