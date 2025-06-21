from typing import Dict, List, Any, Optional, TypedDict
from datetime import datetime
from enum import Enum


class QueryDomain(Enum):
    HR = "hr"
    IT = "it" 
    FINANCE = "finance"
    GENERAL = "general"
    CROSS_DEPARTMENT = "cross_department"


class AccessLevel(Enum):
    PUBLIC = "public"
    INTERNAL = "internal"
    CONFIDENTIAL = "confidential"
    RESTRICTED = "restricted"


class ProcessingStatus(Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    PERMISSION_DENIED = "permission_denied"


class RAGWorkflowState(TypedDict):
    """
    State schema cho LangGraph workflow
    Quản lý toàn bộ state trong quá trình xử lý RAG query với permission control
    """
    
    # Input query và user context
    query: str
    original_query: str
    user_id: str
    tenant_id: str
    session_id: str
    timestamp: datetime
    
    # User permissions và access control
    user_context: Dict[str, Any]
    user_permissions: List[str]
    user_department: str
    user_role: str
    accessible_collections: List[str]
    max_access_level: AccessLevel
    
    # Query analysis results
    domain_classification: List[QueryDomain]
    query_complexity: float
    intent_analysis: Dict[str, Any]
    requires_cross_department: bool
    estimated_processing_time: float
    
    # Tool management
    available_tools: List[str]
    enabled_tools: List[str]
    tool_permissions: Dict[str, List[str]]
    selected_tools: List[str]
    
    # Retrieval results với permission filtering
    raw_retrieval_results: Dict[str, List[Dict[str, Any]]]
    filtered_retrieval_results: Dict[str, List[Dict[str, Any]]]
    permission_filtered_count: int
    total_documents_found: int
    relevance_scores: Dict[str, float]
    
    # Agent responses
    router_decision: Dict[str, Any]
    domain_agent_responses: Dict[str, Dict[str, Any]]
    tool_agent_outputs: Dict[str, Any]
    cross_references: List[Dict[str, Any]]
    
    # Content synthesis và filtering
    raw_synthesis: str
    sanitized_content: str
    redacted_sections: List[str]
    final_response: str
    response_metadata: Dict[str, Any]
    
    # Quality và confidence metrics
    confidence_scores: Dict[str, float]
    quality_metrics: Dict[str, float]
    factual_consistency_score: float
    relevance_score: float
    
    # Security và audit
    access_audit_trail: List[Dict[str, Any]]
    security_violations: List[Dict[str, Any]]
    redacted_content_log: List[Dict[str, Any]]
    permission_checks: List[Dict[str, Any]]
    
    # Processing status
    current_stage: str
    processing_status: ProcessingStatus
    error_messages: List[str]
    warnings: List[str]
    retry_count: int
    
    # Performance tracking
    stage_timestamps: Dict[str, datetime]
    processing_duration: Dict[str, float]
    total_processing_time: float
    cache_hits: Dict[str, bool]


class UserContext(TypedDict):
    """User context information cho permission checking"""
    user_id: str
    username: str
    email: str
    department: str
    role: str
    permissions: List[str]
    access_levels: List[AccessLevel]
    tenant_id: str
    last_login: datetime
    session_expires: datetime


class DocumentMetadata(TypedDict):
    """Document metadata với permission information"""
    document_id: str
    title: str
    content_type: str
    department: str
    access_level: AccessLevel
    required_permissions: List[str]
    author: str
    created_date: datetime
    last_modified: datetime
    version: str
    confidentiality_level: str
    tags: List[str]
    file_path: str
    content_hash: str


class ToolConfig(TypedDict):
    """Tool configuration với permission control"""
    tool_id: str
    tool_name: str
    tool_type: str
    is_enabled: bool
    required_permissions: List[str]
    allowed_departments: List[str]
    max_access_level: AccessLevel
    rate_limit: Optional[int]
    timeout_seconds: int
    configuration: Dict[str, Any]


class AuditLogEntry(TypedDict):
    """Audit log entry cho security tracking"""
    timestamp: datetime
    user_id: str
    action: str
    resource_type: str
    resource_id: str
    access_granted: bool
    permission_checked: List[str]
    ip_address: str
    user_agent: str
    session_id: str
    details: Dict[str, Any]


class StateTransition(TypedDict):
    """State transition tracking"""
    from_stage: str
    to_stage: str
    timestamp: datetime
    trigger: str
    conditions_met: List[str]
    conditions_failed: List[str]
    processing_time: float