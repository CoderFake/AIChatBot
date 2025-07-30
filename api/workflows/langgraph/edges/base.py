"""
Base edge implementations for LangGraph workflows
Edges determine routing logic between nodes
"""
from typing import Dict, Any, List, Optional, Literal
from abc import ABC, abstractmethod

from workflows.langgraph.state.state import RAGState
from utils.logging import get_logger

logger = get_logger(__name__)


class BaseEdge(ABC):
    """
    Abstract base class for workflow edges
    Edges are functions that determine next node based on state
    """
    
    def __init__(self, edge_name: str):
        self.edge_name = edge_name
    
    @abstractmethod
    def route(self, state: RAGState) -> str:
        """
        Determine next node based on state
        
        Args:
            state: Current workflow state
            
        Returns:
            Next node name or END
        """
        pass
    
    def __call__(self, state: RAGState) -> str:
        """Make edge callable following LangGraph pattern"""
        try:
            next_node = self.route(state)
            logger.debug(f"Edge {self.edge_name}: routing to {next_node}")
            return next_node
        except Exception as e:
            logger.error(f"Edge {self.edge_name} failed: {e}")
            return "error"


class ConditionalEdge(BaseEdge):
    """
    Conditional edge that routes based on state conditions
    """
    
    def route_by_condition(self, state: RAGState) -> str:
        """Override in subclasses for specific routing logic"""
        return "END"


class SimpleRouterEdge(BaseEdge):
    """
    Simple router edge based on next_action field
    """
    
    def __init__(self):
        super().__init__("simple_router")
    
    def route(self, state: RAGState) -> str:
        """Route based on next_action field in state"""
        return state.get("next_action", "END")