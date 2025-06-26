"""
Services-specific types
Import common types và định nghĩa thêm các types riêng cho services
"""
from enum import Enum

from common.types import AccessLevel, ProcessingStatus, QueryType, QueryDomain


class ExecutionStrategy(Enum):
    """Chiến lược thực thi query"""
    SINGLE_AGENT = "single_agent"
    MULTI_AGENT = "multi_agent"
    TOOL_ONLY = "tool_only"
    RAG_ONLY = "rag_only"


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
    """Loại index cho vector database"""
    HNSW = "HNSW"
    IVF_FLAT = "IVF_FLAT"
    IVF_SQ8 = "IVF_SQ8"
