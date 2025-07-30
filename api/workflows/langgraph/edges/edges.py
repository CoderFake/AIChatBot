"""
Complete edge implementations for Multi-Agent RAG workflow
Routing logic between workflow nodes
"""
from typing import Dict, Any, List, Literal

from .base import BaseEdge, ConditionalEdge
from workflows.langgraph.state.state import RAGState
from utils.logging import get_logger

logger = get_logger(__name__)


class OrchestratorRouter(ConditionalEdge):
    """
    Routes from orchestrator to reflection_router or agent_execution
    Based on query complexity analysis
    """
    
    def __init__(self):
        super().__init__("orchestrator_router")
    
    def route(self, state: RAGState) -> Literal["reflection_router", "agent_execution", "error"]:
        """
        Route based on orchestrator decision
        """
        try:
            next_action = state.get("next_action")
            
            if next_action == "reflection_router":
                return "reflection_router"
            elif next_action == "agent_execution":
                return "agent_execution"
            else:
                logger.warning(f"Unexpected next_action from orchestrator: {next_action}")
                return "error"
                
        except Exception as e:
            logger.error(f"Orchestrator routing failed: {e}")
            return "error"


class ReflectionRouter(ConditionalEdge):
    """
    Routes from reflection_semantic_router to agent_execution
    Always goes to agent execution after analysis
    """
    
    def __init__(self):
        super().__init__("reflection_router")
    
    def route(self, state: RAGState) -> Literal["agent_execution", "error"]:
        """
        Route after reflection and semantic analysis
        """
        try:
            query_analysis = state.get("query_analysis")
            
            if query_analysis and query_analysis.get("selected_agents"):
                return "agent_execution"
            else:
                logger.error("No agents selected in query analysis")
                return "error"
                
        except Exception as e:
            logger.error(f"Reflection routing failed: {e}")
            return "error"


class AgentExecutionRouter(ConditionalEdge):
    """
    Routes from agent_execution to conflict_resolution or final_response
    Based on number of successful agent responses
    """
    
    def __init__(self):
        super().__init__("agent_execution_router")
    
    def route(self, state: RAGState) -> Literal["conflict_resolution", "final_response", "error"]:
        """
        Route based on agent execution results
        """
        try:
            agent_responses = state.get("agent_responses", [])
            
            successful_responses = [
                resp for resp in agent_responses 
                if resp.get("status") == "completed" and resp.get("content")
            ]
            
            if len(successful_responses) == 0:
                logger.error("No successful agent responses")
                return "error"
            elif len(successful_responses) == 1:
                return "final_response"
            else:
                return "conflict_resolution"
                
        except Exception as e:
            logger.error(f"Agent execution routing failed: {e}")
            return "error"


class ConflictResolutionRouter(ConditionalEdge):
    """
    Routes from conflict_resolution to final_response
    Always goes to final response after conflict resolution
    """
    
    def __init__(self):
        super().__init__("conflict_resolution_router")
    
    def route(self, state: RAGState) -> Literal["final_response", "error"]:
        """
        Route after conflict resolution
        """
        try:
            conflict_resolution = state.get("conflict_resolution")
            
            if conflict_resolution and conflict_resolution.get("final_answer"):
                return "final_response"
            else:
                logger.warning("Conflict resolution incomplete, proceeding to final response")
                return "final_response"
                
        except Exception as e:
            logger.error(f"Conflict resolution routing failed: {e}")
            return "error"


class ErrorRouter(ConditionalEdge):
    """
    Routes for error handling and recovery
    """
    
    def __init__(self):
        super().__init__("error_router")
    
    def route(self, state: RAGState) -> Literal["final_response", "END"]:
        """
        Route for error scenarios
        """
        try:
            retry_count = state.get("retry_count", 0)
            max_retries = 2
            
            if retry_count < max_retries:
                return "final_response"
            else:
                return "END"
                
        except Exception as e:
            logger.error(f"Error routing failed: {e}")
            return "END"


def create_orchestrator_router():
    """Create orchestrator router function for LangGraph"""
    router = OrchestratorRouter()
    return router.route


def create_reflection_router():
    """Create reflection router function for LangGraph"""
    router = ReflectionRouter()
    return router.route


def create_agent_execution_router():
    """Create agent execution router function for LangGraph"""
    router = AgentExecutionRouter()
    return router.route


def create_conflict_resolution_router():
    """Create conflict resolution router function for LangGraph"""
    router = ConflictResolutionRouter()
    return router.route


def create_error_router():
    """Create error router function for LangGraph"""
    router = ErrorRouter()
    return router.route