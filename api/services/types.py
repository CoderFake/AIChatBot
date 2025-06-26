from enum import Enum

class QueryType(Enum):
    RAG_QUERY = "rag_query"
    CHITCHAT = "chitchat"
    ACTION_REQUEST = "action_request"
    CLARIFICATION = "clarification"

class ExecutionStrategy(Enum):
    SINGLE_AGENT = "single_agent"
    MULTI_AGENT = "multi_agent"
    TOOL_ONLY = "tool_only"
    RAG_ONLY = "rag_only"


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


class AgentRole(Enum):
    """Vai trò của các agents trong hệ thống"""
    COORDINATOR = "coordinator"
    HR_SPECIALIST = "hr_specialist" 
    FINANCE_SPECIALIST = "finance_specialist"
    IT_SPECIALIST = "it_specialist"
    GENERAL_ASSISTANT = "general_assistant"
    CONFLICT_RESOLVER = "conflict_resolver"
    SYNTHESIZER = "synthesizer"

class ConflictLevel(Enum):
    """Mức độ xung đột giữa các agents"""
    NONE = "none"
    LOW = "low"      # Confidence gap < 0.3
    MEDIUM = "medium" # Confidence gap 0.3-0.6
    HIGH = "high"    # Confidence gap > 0.6

class ConsensusStatus(Enum):
    """Trạng thái đồng thuận"""
    PENDING = "pending"
    ACHIEVED = "achieved" 
    FAILED = "failed"
    ESCALATED = "escalated"


class IndexType(Enum):
    HNSW = "HNSW"
    IVF_FLAT = "IVF_FLAT"
    IVF_SQ8 = "IVF_SQ8"
