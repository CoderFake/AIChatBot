from dataclasses import dataclass
from typing import Dict, Any, List

from services.types import QueryType, ExecutionStrategy

@dataclass
class QueryAnalysis:
    """Kết quả phân tích query ban đầu"""
    refined_query: str
    query_type: QueryType
    language: str
    confidence: float
    reasoning: str
    conversation_context: Dict[str, Any]

@dataclass
class TaskDistribution:
    """Phân phối nhiệm vụ cho agents"""
    strategy: ExecutionStrategy
    selected_agents: List[str]
    sub_queries: Dict[str, str]
    agent_configs: Dict[str, Dict[str, Any]]
    reasoning: str

@dataclass
class ToolSelection:
    """Lựa chọn tools cho execution"""
    selected_tools: List[str]
    tool_configs: Dict[str, Dict[str, Any]]
    usage_strategy: str
    reasoning: str

@dataclass
class ConflictResolution:
    """Giải quyết xung đột giữa agents"""
    winning_response: str
    evidence_ranking: List[Dict[str, Any]]
    conflict_explanation: str
    confidence_score: float
