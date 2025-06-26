from dataclasses import dataclass, field
from typing import Any, Dict, Optional, List
from utils.datetime_utils import CustomDateTime as datetime

from common.types import ConfigChangeType, ConfigScope


@dataclass
class ConfigChange:
    """Configuration change event"""
    change_type: ConfigChangeType
    component_name: str
    old_value: Any
    new_value: Any
    user_id: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.now)
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
