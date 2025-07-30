"""
Main state definition for RAG workflow
Complete state management following LangGraph patterns
"""
from typing import TypedDict, List, Dict, Any, Optional, Sequence, Annotated, Literal
from typing_extensions import NotRequired
from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages
import operator

from .base import UserContext, QueryAnalysisResult, AgentResponse, ConflictResolution
from common.types import AccessLevel, ProcessingStatus


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
    
    # === Workflow Control ===
    current_step: str
    next_action: NextAction
    processing_status: ProcessingStatus
    
    # === Query Analysis (from Reflection + Semantic Router) ===
    query_analysis: NotRequired[QueryAnalysisResult]
    
    # === Agent Execution Results ===
    agent_responses: Annotated[List[AgentResponse], operator.add]
    
    # === Tool Results ===
    tool_results: NotRequired[Dict[str, Any]]
    
    # === Conflict Resolution ===
    conflict_resolution: NotRequired[ConflictResolution]
    
    # === Final Output ===
    final_response: NotRequired[str]
    final_sources: Annotated[List[str], operator.add]
    
    # === Error Handling ===
    error_message: NotRequired[str]
    retry_count: NotRequired[int]
    
    # === Debug and Metadata ===
    execution_metadata: NotRequired[Dict[str, Any]]
    debug_trace: Annotated[List[str], operator.add]


# Alias for backward compatibility
RAGWorkflowState = RAGState
UnifiedRAGState = RAGState