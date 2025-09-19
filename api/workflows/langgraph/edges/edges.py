"""
Updated edge implementations for Multi-Agent RAG workflow with planning
"""
from typing import Literal
from .base import  ConditionalEdge
from workflows.langgraph.state.state import RAGState
from utils.logging import get_logger

logger = get_logger(__name__)


class OrchestratorRouter(ConditionalEdge):
    """
    Routes from orchestrator to semantic_reflection or direct execution
    """
    
    def __init__(self):
        super().__init__("orchestrator_router")
    
    def route(self, state: RAGState) -> Literal["semantic_reflection", "execute_planning", "error"]:
        """
        Route based on orchestrator decision
        """
        try:
            next_action = state.get("next_action")
            
            if next_action == "semantic_reflection":
                return "semantic_reflection"
            elif next_action == "execute_planning":
                return "execute_planning"
            else:
                logger.warning(f"Unexpected next_action from orchestrator: {next_action}")
                return "error"
                
        except Exception as e:
            logger.error(f"Execute planning routing failed: {e}")
            return "error"


class ConflictResolutionRouter(ConditionalEdge):
    """
    Routes from conflict_resolution to final_response
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
            
            agent_responses = state.get("agent_responses", [])
            if agent_responses:
                return "final_response"
            
            return "error"
            
        except Exception as e:
            logger.error(f"Conflict resolution routing failed: {e}")
            return "error"


class ErrorRouter(ConditionalEdge):
    """
    Routes from error states
    """
    
    def __init__(self):
        super().__init__("error_router")
    
    def route(self, state: RAGState) -> Literal["final_response"]:
        """
        Always route to final_response for error handling
        """
        return "final_response"


def create_orchestrator_router() -> OrchestratorRouter:
    """Create orchestrator router"""
    return OrchestratorRouter()


def create_semantic_reflection_router() -> "SemanticReflectionRouter":
    """Create semantic reflection router"""
    return SemanticReflectionRouter()


def create_execute_planning_router() -> "ExecutePlanningRouter":
    """Create execute planning router"""
    return ExecutePlanningRouter()


def create_conflict_resolution_router() -> ConflictResolutionRouter:
    """Create conflict resolution router"""
    return ConflictResolutionRouter()


def create_error_router() -> ErrorRouter:
    """Create error router"""
    return ErrorRouter()


class SemanticReflectionRouter(ConditionalEdge):
    """
    Routes from semantic_reflection based on analysis results
    """
    
    def __init__(self):
        super().__init__("semantic_reflection_router")
    
    def route(self, state: RAGState) -> Literal["execute_planning", "final_response", "error"]:
        """
        Route after semantic reflection - simplified flow
        """
        try:
            next_action = state.get("next_action")

            if next_action == "final_response":
                return "final_response"
            elif next_action == "execute_planning":
                return "execute_planning"
            else:
                semantic_routing = state.get("semantic_routing")
                if semantic_routing and semantic_routing.get("is_chitchat"):
                    return "final_response"
                elif state.get("execution_plan"):
                    return "execute_planning"
                else:
                    return "error"

        except Exception as e:
            logger.error(f"Semantic reflection routing failed: {e}")
            return "error"


class ExecutePlanningRouter(ConditionalEdge):
    """
    Routes from execute_planning based on completion status
    """
    
    def __init__(self):
        super().__init__("execute_planning_router")
    
    def route(self, state: RAGState) -> Literal["conflict_resolution", "final_response", "error"]:
        """
        Route after planning execution using routing_decision from node
        """
        try:
            error_message = state.get("error_message")
            if error_message:
                return "error"

            routing_decision = state.get("routing_decision")

            if routing_decision == "single_agent_sequential":
                return "final_response"
            elif routing_decision == "multiple_agents":
                return "conflict_resolution"
            elif routing_decision == "complex":
                return "conflict_resolution"  
            agent_responses = state.get("agent_responses", [])
            if agent_responses:
                if len(agent_responses) == 1:
                    return "final_response"
                else:
                    return "conflict_resolution"

            return "error"

        except Exception as e:
            logger.error(f"Execute planning routing failed: {e}")
            return "error"