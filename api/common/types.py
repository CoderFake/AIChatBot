"""
Common types and enums for the entire system
Single source of truth to avoid duplicates and ensure consistency
"""
from enum import Enum
from typing import Set, List, Dict

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

ROLE_LEVEL = {
    "MAINTAINER": 5,
    "ADMIN": 4,
    "DEPT_ADMIN": 3,
    "DEPT_MANAGER": 2,
    "USER": 1,
}


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
    """Enum define allowed file types"""
    PDF = "pdf"
    DOCX = "docx"
    DOC = "doc"
    MD = "md"
    TXT = "txt"


# File validation constants
ALLOWED_MIME_TYPES = {
    'application/pdf',  # PDF files
    'application/msword',  # DOC files
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document',  # DOCX files
    'text/plain',  # TXT files
    'text/markdown',  # MD files
    'text/x-markdown'  # Alternative MD MIME type
}

MIME_TYPE_MAPPING = {
    'application/pdf': 'pdf',
    'application/msword': 'doc',
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document': 'docx',
    'text/plain': 'txt',
    'text/markdown': 'md',
    'text/x-markdown': 'md'
}


def validate_file_type(mime_type: str) -> str:
    """
    Validate file type and return short name.
    Raises ValueError if file type is not allowed.

    Args:
        mime_type: MIME type of the file

    Returns:
        Short file type name

    Raises:
        ValueError: If file type is not in allowed list
    """
    if mime_type not in ALLOWED_MIME_TYPES:
        raise ValueError("File type not allowed. Only PDF, DOCX, DOC, MD, and TXT files are supported.")
    return MIME_TYPE_MAPPING.get(mime_type, 'unknown')


def is_allowed_file_type(mime_type: str) -> bool:
    """
    Check if file type is allowed.

    Args:
        mime_type: MIME type of the file

    Returns:
        True if allowed, False otherwise
    """
    return mime_type in ALLOWED_MIME_TYPES


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



class Permission(Enum):
    """All available permissions in the system"""
    
    # Maintainer permissions
    TENANT_CREATE = "tenant.create"
    TENANT_READ = "tenant.read"
    TENANT_UPDATE = "tenant.update"
    TENANT_DELETE_SOFT = "tenant.delete.soft"
    TENANT_DELETE_HARD = "tenant.delete.hard"
    TOOL_ENABLE_TENANT = "tool.enable.tenant"
    TOOL_DISABLE_TENANT = "tool.disable.tenant"
    
    # Admin permissions
    USER_GROUP_CREATE = "user.group.create"
    USER_GROUP_READ = "user.group.read"
    USER_GROUP_UPDATE = "user.group.update"
    USER_GROUP_DELETE = "user.group.delete"
    USER_PERMISSION_MANAGE = "user.permission.manage"
    DEPT_CREATE = "department.create"
    DEPT_READ = "department.read"
    DEPT_UPDATE = "department.update"
    DEPT_DELETE = "department.delete"
    AGENT_CREATE = "agent.create"
    AGENT_READ = "agent.read"
    AGENT_UPDATE = "agent.update"
    AGENT_DELETE = "agent.delete"
    TOOL_ENABLE_DEPT = "tool.enable.department"
    TOOL_DISABLE_DEPT = "tool.disable.department"
    INVITE_DEPT_ADMIN = "invite.dept.admin"
    INVITE_DEPT_MANAGER = "invite.dept.manager"
    
    # Dept Admin permissions
    PROVIDER_CONFIG = "provider.configure"
    TOOL_CONFIG_DEPT = "tool.configure.department"
    
    # Dept Manager permissions
    DOCUMENT_PRIVATE_CREATE = "document.private.create"
    DOCUMENT_PRIVATE_READ = "document.private.read"
    DOCUMENT_PRIVATE_UPDATE = "document.private.update"
    DOCUMENT_PRIVATE_DELETE = "document.private.delete"
    DOCUMENT_PUBLIC_CREATE = "document.public.create"
    DOCUMENT_PUBLIC_READ = "document.public.read"
    DOCUMENT_PUBLIC_UPDATE = "document.public.update"
    DOCUMENT_PUBLIC_DELETE = "document.public.delete"
    CHAT_PRIVATE = "chat.private"
    CHAT_PUBLIC = "chat.public"
    
    # User permissions
    AUTH_LOGIN = "auth.login"
    AUTH_LOGOUT = "auth.logout"
    CHAT_PUBLIC_ONLY = "chat.public.only"


class RolePermissions:
    """
    Define default permissions for each role
    """
    
    MAINTAINER_PERMISSIONS = {
        Permission.TENANT_CREATE,
        Permission.TENANT_READ,
        Permission.TENANT_UPDATE,
        Permission.TENANT_DELETE_SOFT,
        Permission.TENANT_DELETE_HARD,
        Permission.TOOL_ENABLE_TENANT,
        Permission.TOOL_DISABLE_TENANT,
    }
    
    ADMIN_PERMISSIONS = {
        Permission.USER_GROUP_CREATE,
        Permission.USER_GROUP_READ,
        Permission.USER_GROUP_UPDATE,
        Permission.USER_GROUP_DELETE,
        Permission.USER_PERMISSION_MANAGE,
        Permission.DEPT_CREATE,
        Permission.DEPT_READ,
        Permission.DEPT_UPDATE,
        Permission.DEPT_DELETE,
        Permission.AGENT_CREATE,
        Permission.AGENT_READ,
        Permission.AGENT_UPDATE,
        Permission.AGENT_DELETE,
        Permission.TOOL_ENABLE_DEPT,
        Permission.TOOL_DISABLE_DEPT,
        Permission.INVITE_DEPT_ADMIN,
        Permission.INVITE_DEPT_MANAGER,
        # Inherit Dept Admin permissions
        Permission.PROVIDER_CONFIG,
        Permission.TOOL_CONFIG_DEPT,
        # Inherit Dept Manager permissions
        Permission.DOCUMENT_PRIVATE_CREATE,
        Permission.DOCUMENT_PRIVATE_READ,
        Permission.DOCUMENT_PRIVATE_UPDATE,
        Permission.DOCUMENT_PRIVATE_DELETE,
        Permission.DOCUMENT_PUBLIC_CREATE,
        Permission.DOCUMENT_PUBLIC_READ,
        Permission.DOCUMENT_PUBLIC_UPDATE,
        Permission.DOCUMENT_PUBLIC_DELETE,
        Permission.CHAT_PRIVATE,
        Permission.CHAT_PUBLIC,
    }
    
    DEPT_ADMIN_PERMISSIONS = {
        Permission.PROVIDER_CONFIG,
        Permission.TOOL_CONFIG_DEPT,
        Permission.INVITE_DEPT_MANAGER,
        # Inherit Dept Manager permissions
        Permission.DOCUMENT_PRIVATE_CREATE,
        Permission.DOCUMENT_PRIVATE_READ,
        Permission.DOCUMENT_PRIVATE_UPDATE,
        Permission.DOCUMENT_PRIVATE_DELETE,
        Permission.DOCUMENT_PUBLIC_CREATE,
        Permission.DOCUMENT_PUBLIC_READ,
        Permission.DOCUMENT_PUBLIC_UPDATE,
        Permission.DOCUMENT_PUBLIC_DELETE,
        Permission.CHAT_PRIVATE,
        Permission.CHAT_PUBLIC,
    }
    
    DEPT_MANAGER_PERMISSIONS = {
        Permission.DOCUMENT_PRIVATE_CREATE,
        Permission.DOCUMENT_PRIVATE_READ,
        Permission.DOCUMENT_PRIVATE_UPDATE,
        Permission.DOCUMENT_PRIVATE_DELETE,
        Permission.DOCUMENT_PUBLIC_CREATE,
        Permission.DOCUMENT_PUBLIC_READ,
        Permission.DOCUMENT_PUBLIC_UPDATE,
        Permission.DOCUMENT_PUBLIC_DELETE,
        Permission.CHAT_PRIVATE,
        Permission.CHAT_PUBLIC,
    }
    
    USER_PERMISSIONS = {
        Permission.AUTH_LOGIN,
        Permission.AUTH_LOGOUT,
        Permission.CHAT_PUBLIC_ONLY,
    }
    
    @classmethod
    def get_permissions_for_role(cls, role: UserRole) -> Set[Permission]:
        """
        Get all permissions for a specific role
        """
        role_map = {
            UserRole.MAINTAINER: cls.MAINTAINER_PERMISSIONS,
            UserRole.ADMIN: cls.ADMIN_PERMISSIONS,
            UserRole.DEPT_ADMIN: cls.DEPT_ADMIN_PERMISSIONS,
            UserRole.DEPT_MANAGER: cls.DEPT_MANAGER_PERMISSIONS,
            UserRole.USER: cls.USER_PERMISSIONS,
        }
        return role_map.get(role, set())
    
    @classmethod
    def get_permission_values_for_role(cls, role: UserRole) -> List[str]:
        """
        Get permission string values for a role
        """
        permissions = cls.get_permissions_for_role(role)
        return [perm.value for perm in permissions]


class DefaultGroupNames:
    """
    Default group names for tenant
    """
    ADMIN = "Administrators"
    DEPT_ADMIN = "Department Administrators"
    DEPT_MANAGER = "Department Managers"
    USER = "Users"
    
    DESCRIPTIONS = {
        ADMIN: "Full administrative access within tenant",
        DEPT_ADMIN: "Department-level administrative access",
        DEPT_MANAGER: "Department document and chat management",
        USER: "Basic user access with public chat only"
    }


class DefaultProviderConfig:
    """
    Default provider configuration
    """
    PROVIDER_NAME = "gemini"
    DEFAULT_MODEL = "gemini-1.5-flash"
    DEFAULT_TEMPERATURE = 0.7
    DEFAULT_MAX_TOKENS = 2048
    
    @classmethod
    def get_default_config(cls) -> Dict:
        return {
            "provider": cls.PROVIDER_NAME,
            "model": cls.DEFAULT_MODEL,
            "temperature": cls.DEFAULT_TEMPERATURE,
            "max_tokens": cls.DEFAULT_MAX_TOKENS
        }


class DocumentAccessLevel(Enum):
    """Document access level enum"""
    PUBLIC = "public"
    PRIVATE = "private"


class DocumentProcessingStatus(Enum):
    """Document processing status enum"""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class VectorProcessingStatus(Enum):
    """Vector processing status enum"""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class KafkaMessageStatus(Enum):
    """Kafka message status enum"""
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    COMPLETED_WITH_ERRORS = "completed_with_errors"


class DocumentConstants:
    """Constants for document operations to avoid hardcoding"""
    
    ROOT_FOLDER_PATH = "/"
    ROOT_FOLDER_NAME = "root"
    
    COLLECTION_NAME_TEMPLATE_PUBLIC = "{department_id}_public"
    COLLECTION_NAME_TEMPLATE_PRIVATE = "{department_id}_private"
    
    # Bucket name template
    BUCKET_NAME_TEMPLATE = "{prefix}-{tenant_id}"
    
    STORAGE_KEY_TEMPLATE = "{tenant_id}/{department_id}/{document_uuid}_{filename}"
    
    # Progress steps for Kafka
    PROGRESS_START = 5
    PROGRESS_STORAGE_UPLOADED = 20
    PROGRESS_DB_CREATED = 35
    PROGRESS_CHUNKS_EXTRACTED = 70
    PROGRESS_STORAGE_DELETED = 35
    PROGRESS_DB_DELETED = 65
    PROGRESS_COMPLETED = 100
    
    # Batch processing
    DEFAULT_BATCH_SEMAPHORE_LIMIT = 4
