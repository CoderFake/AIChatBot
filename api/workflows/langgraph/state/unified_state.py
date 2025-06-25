from typing import Dict, List, Any, Optional, TypedDict, Annotated
from datetime import datetime
from enum import Enum

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages

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

class UnifiedRAGState(TypedDict):
    """
    Unified state schema cho tất cả RAG workflows
    Merge RAGState và RAGWorkflowState
    """
    
    # LangGraph messages
    messages: Annotated[List[BaseMessage], add_messages]
    
    # Core query information  
    original_query: str
    processed_query: str
    query: str  # Alias for compatibility
    language: str
    
    # User context và permissions
    user_id: Optional[str]
    tenant_id: Optional[str]
    session_id: str
    user_context: Dict[str, Any]
    user_permissions: List[str]
    user_department: str
    user_role: str
    accessible_collections: List[str]
    max_access_level: AccessLevel
    
    # Query analysis
    domain_classification: List[QueryDomain]
    query_complexity: float
    complexity_score: float  # Alias for compatibility
    intent_analysis: Dict[str, Any]
    requires_cross_department: bool
    estimated_processing_time: float
    
    # Agent orchestration
    selected_agents: List[str]
    agent_outputs: Dict[str, Dict[str, Any]]
    orchestrator_reasoning: str
    domain_agent_responses: Dict[str, Dict[str, Any]]
    router_decision: Dict[str, Any]
    cross_references: List[Dict[str, Any]]
    
    # Tool management
    available_tools: List[str]
    enabled_tools: List[str]
    tool_permissions: Dict[str, List[str]]
    selected_tools: List[str]
    tool_calls: List[Dict[str, Any]]
    tool_outputs: List[Dict[str, Any]]
    tool_agent_outputs: Dict[str, Any]
    
    # Document retrieval
    raw_retrieval_results: Dict[str, List[Dict[str, Any]]]
    filtered_retrieval_results: Dict[str, List[Dict[str, Any]]]
    retrieved_documents: List[Dict[str, Any]]  # Alias for compatibility
    document_sources: List[str]
    permission_filtered_count: int
    total_documents_found: int
    relevance_scores: Dict[str, float]
    
    # Response generation
    raw_synthesis: str
    sanitized_content: str
    draft_response: str
    final_response: str
    response_metadata: Dict[str, Any]
    redacted_sections: List[str]
    
    # Quality và confidence
    confidence_scores: Dict[str, float]
    confidence_score: float  # Alias for compatibility
    quality_metrics: Dict[str, float]
    quality_checks: Dict[str, bool]
    factual_consistency_score: float
    relevance_score: float
    
    # Security
    content_safety: Dict[str, Any]
    access_audit_trail: List[Dict[str, Any]]
    security_violations: List[Dict[str, Any]]
    redacted_content_log: List[Dict[str, Any]]
    permission_checks: List[Dict[str, Any]]
    
    # Processing status và control
    current_stage: str
    processing_status: ProcessingStatus
    workflow_id: str
    error_messages: List[str]
    warnings: List[str]
    retry_count: int
    iteration_count: int
    
    # Performance tracking
    timestamp: datetime
    stage_timestamps: Dict[str, datetime]
    processing_duration: Dict[str, float]
    processing_time: float
    total_processing_time: float
    cache_hits: Dict[str, bool]
    
    # Conversation context
    conversation_history: List[Dict[str, Any]]

# Aliases for backward compatibility
RAGState = UnifiedRAGState
RAGWorkflowState = UnifiedRAGState 