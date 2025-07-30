"""
Base node implementations for LangGraph workflows
All nodes follow the pattern: State -> Partial[State]
"""
from typing import Dict, Any, Optional
from abc import ABC, abstractmethod
from langchain_core.runnables import RunnableConfig

from workflows.langgraph.state.state import RAGState
from utils.logging import get_logger

logger = get_logger(__name__)


class BaseWorkflowNode(ABC):
    """
    Abstract base class for all workflow nodes
    Follows LangGraph pattern: nodes receive State and return partial State
    """
    
    def __init__(self, node_name: str):
        self.node_name = node_name
    
    @abstractmethod
    async def execute(self, state: RAGState, config: RunnableConfig) -> Dict[str, Any]:
        """
        Execute node logic
        
        Args:
            state: Current workflow state
            config: LangGraph runtime configuration
            
        Returns:
            Partial state update
        """
        pass
    
    def __call__(self, state: RAGState, config: RunnableConfig) -> Dict[str, Any]:
        """Make node callable following LangGraph pattern"""
        try:
            logger.info(f"Executing node: {self.node_name}")
            result = self.execute(state, config)
            
            debug_update = {
                "debug_trace": [f"{self.node_name}: executed successfully"],
                "current_step": self.node_name
            }
            
            if isinstance(result, dict):
                result.update(debug_update)
            else:
                result = debug_update
            
            return result
            
        except Exception as e:
            logger.error(f"Node {self.node_name} failed: {e}")
            return {
                "error_message": f"Node {self.node_name} failed: {str(e)}",
                "processing_status": "failed",
                "debug_trace": [f"{self.node_name}: failed with error: {str(e)}"]
            }


class AnalysisNode(BaseWorkflowNode):
    """
    Base class for analysis nodes that process queries
    """
    
    async def analyze_query(
        self, 
        query: str, 
        user_context: Dict[str, Any],
        config: RunnableConfig
    ) -> Dict[str, Any]:
        """Override in subclasses for specific analysis logic"""
        return {}


class ExecutionNode(BaseWorkflowNode):
    """
    Base class for execution nodes that run agents/tools
    """
    
    async def execute_task(
        self,
        task_info: Dict[str, Any],
        user_context: Dict[str, Any],
        config: RunnableConfig
    ) -> Dict[str, Any]:
        """Override in subclasses for specific execution logic"""
        return {}