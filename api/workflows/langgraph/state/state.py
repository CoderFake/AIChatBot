"""
Main state definition for RAG workflow
Complete state management following LangGraph patterns
"""
from typing import TypedDict, List, Dict, Any, Sequence, Annotated, Literal
from typing_extensions import NotRequired
from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages
import operator

from .base import UserContext, QueryAnalysisResult, AgentResponse, ConflictResolution
from common.types import ProcessingStatus


NextAction = Literal["orchestrator", "reflection_router", "agent_execution", "conflict_resolution", "final_response", "error"]


class RAGState(TypedDict):
    """
    Complete state for Multi-Agent RAG workflow
    """
    # === Core Input ===
    query: str
    messages: Annotated[Sequence[BaseMessage], add_messages]

    # === User Context ===
    user_context: UserContext

    # === Execution Context (flattened for easy access) ===
    user_id: NotRequired[str]
    tenant_id: NotRequired[str]
    department_id: NotRequired[str]
    access_scope: NotRequired[str]
    provider: NotRequired[Any]
    agents_structure: NotRequired[Dict[str, Any]]
    agent_providers: NotRequired[Dict[str, Any]]

    # === Workflow Control ===
    current_step: NotRequired[str]
    next_action: NextAction
    processing_status: ProcessingStatus

    # === Progress Tracking ===
    progress_percentage: NotRequired[int]
    progress_message: NotRequired[str]
    should_yield: NotRequired[bool]

    # === Query Analysis (from Reflection + Semantic Router) ===
    query_analysis: NotRequired[QueryAnalysisResult]
    semantic_routing: NotRequired[Dict[str, Any]]
    detected_language: NotRequired[str]
    is_chitchat: NotRequired[bool]
    chitchat_response: NotRequired[str]
    execution_plan: NotRequired[Dict[str, Any]]
    routing_decision: NotRequired[str]

    # === Summary History ===
    summary_history: NotRequired[str]

    # === Agent Execution Results ===
    agent_responses: Annotated[List[AgentResponse], operator.add]

    # === Tool Results ===
    tool_results: NotRequired[Dict[str, Any]]

    # === Conflict Resolution ===
    conflict_resolution: NotRequired[ConflictResolution]

    # === Final Output ===
    final_response: NotRequired[str]
    final_sources: Annotated[List[str], operator.add]

    # === Presentation Layer ===
    bot_name: NotRequired[str]
    organization_name: NotRequired[str]
    tenant_description: NotRequired[str]

    # === Error Handling ===
    error_message: NotRequired[str]
    original_error: NotRequired[str]
    exception_type: NotRequired[str]
    retry_count: NotRequired[int]

    # === Debug and Metadata ===
    execution_metadata: NotRequired[Dict[str, Any]]
    debug_trace: Annotated[List[str], operator.add]


# Alias for backward compatibility
RAGWorkflowState = RAGState
UnifiedRAGState = RAGState