"""
Base state definitions for LangGraph workflows
"""
from typing import TypedDict, List, Dict, Any, Optional, Sequence, Annotated
from typing_extensions import NotRequired
from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages
import operator


class BaseState(TypedDict):
    """
    Base state schema for LangGraph workflows
    Contains minimal fields required for all workflows
    """
    timestamp: NotRequired[str]
    debug_info: NotRequired[Dict[str, Any]]


class UserContext(TypedDict):
    """User context information for permission checking"""
    user_id: Optional[str]
    session_id: Optional[str] 
    department: Optional[str]
    role: Optional[str]
    permissions: NotRequired[Dict[str, Any]]


class QueryAnalysisResult(TypedDict):
    """Result of query analysis from reflection + semantic router"""
    clarified_query: str
    confidence: float
    query_domain: str  
    selected_agents: List[str]  
    sub_queries: Dict[str, str]
    reasoning: str


class AgentResponse(TypedDict):
    """Response from individual agent execution"""
    agent_name: str
    content: str
    confidence: float
    tools_used: List[str]
    sources: List[str]
    execution_time: float
    status: str


class ConflictResolution(TypedDict):
    """Result of conflict resolution between agents"""
    final_answer: str
    winning_agents: List[str]
    conflict_level: str
    resolution_method: str
    evidence_ranking: List[Dict[str, Any]]


class RAGWorkflowState(TypedDict):
    """
    Main state for RAG workflow following LangGraph best practices
    State is passed between nodes and can be updated using reducers
    """
    # Input query and messages
    query: str
    messages: Annotated[Sequence[BaseMessage], add_messages]
    
    # User context for permissions
    user_context: UserContext
    
    # Workflow control
    current_step: str
    next_action: str
    processing_status: str
    
    # Query analysis results
    query_analysis: NotRequired[QueryAnalysisResult]
    
    # Agent execution results
    agent_responses: Annotated[List[AgentResponse], operator.add]
    
    # Tool execution results
    tool_results: NotRequired[Dict[str, Any]]
    
    # Conflict resolution
    conflict_resolution: NotRequired[ConflictResolution]
    
    # Final response
    final_response: NotRequired[str]
    final_sources: Annotated[List[str], operator.add]
    
    # Error handling
    error_message: NotRequired[str]
    retry_count: NotRequired[int]
    
    # Debug and metadata
    execution_metadata: NotRequired[Dict[str, Any]]