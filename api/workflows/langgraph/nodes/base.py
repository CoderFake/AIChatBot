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

    def __init__(self, node_name: str, timeout_seconds: int = None):
        self.node_name = node_name

        if timeout_seconds is None:
            from config.settings import get_settings
            settings = get_settings()
            self.timeout_seconds = settings.workflow.node_timeouts.get(node_name, 120)
        else:
            self.timeout_seconds = timeout_seconds

        self._timeout = self.timeout_seconds
    
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

    async def __call__(self, state: RAGState, config: RunnableConfig) -> Dict[str, Any]:
        """Make node callable following LangGraph pattern"""
        import asyncio

        try:
            logger.info(f"Executing node: {self.node_name}")
            result = await self.execute(state, config)

            debug_update = {
                "debug_trace": [f"{self.node_name}: executed successfully"],
                "current_step": self.node_name
            }

            if isinstance(result, dict):
                result.update(debug_update)
            else:
                result = debug_update

            return result

        except asyncio.CancelledError:
            raise
        except Exception as e:
            import traceback
            logger.error(f"Node {self.node_name} failed: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            
            error_info = {
                "node_name": self.node_name,
                "error_type": type(e).__name__,
                "error_message": str(e),
                "traceback": traceback.format_exc()
            }
            
            return {
                "error_message": f"Node {self.node_name} failed: {str(e)}",
                "processing_status": "failed",
                "debug_trace": [f"{self.node_name}: failed with error: {str(e)}"],
                "error_details": error_info,
                "next_action": "error"
            }

    def get_localized_message(self, key: str, detected_language: str, **kwargs) -> str:
        """
        Get localized message based on detected language
        NOTE: Use utils.language_utils.get_localized_message() instead
        """
        from utils.language_utils import get_localized_message
        return get_localized_message(key, detected_language, **kwargs)


class AnalysisNode(BaseWorkflowNode):
    """
    Base class for analysis nodes that process queries
    """
    
    def analyze_query(
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
    
    def execute_task(
        self,
        task_info: Dict[str, Any],
        user_context: Dict[str, Any],
        config: RunnableConfig
    ) -> Dict[str, Any]:
        """Override in subclasses for specific execution logic"""
        return {}