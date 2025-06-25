from typing import Dict, Any, Optional
from abc import ABC, abstractmethod
from datetime import datetime

from ..state.unified_state import UnifiedRAGState
from config.settings import get_settings
from utils.logging import get_logger

logger = get_logger(__name__)

class BaseWorkflowNode(ABC):
    """
    Base class cho tất cả workflow nodes
    Giảm code duplication và cung cấp common functionality
    """
    
    def __init__(self):
        self.settings = get_settings()
        self.node_name = self.__class__.__name__
        
    async def __call__(self, state: UnifiedRAGState) -> UnifiedRAGState:
        """Main entry point với error handling và logging"""
        start_time = datetime.now()
        
        try:
            logger.debug(f"{self.node_name} processing started")
            
            # Pre-processing hooks
            state = await self._pre_process(state)
            
            # Main processing
            result_state = await self.process(state)
            
            # Post-processing hooks
            result_state = await self._post_process(result_state, start_time)
            
            logger.debug(f"{self.node_name} processing completed")
            return result_state
            
        except Exception as e:
            logger.error(f"{self.node_name} processing failed: {e}")
            return await self._handle_error(state, e)
    
    @abstractmethod
    async def process(self, state: UnifiedRAGState) -> UnifiedRAGState:
        """Main processing logic - must be implemented by subclasses"""
        pass
    
    async def _pre_process(self, state: UnifiedRAGState) -> UnifiedRAGState:
        """Pre-processing hook - can be overridden"""
        # Update current stage
        return {
            **state,
            "current_stage": self.node_name.lower().replace("node", ""),
            "stage_timestamps": {
                **state.get("stage_timestamps", {}),
                self.node_name.lower(): datetime.now()
            }
        }
    
    async def _post_process(self, state: UnifiedRAGState, start_time: datetime) -> UnifiedRAGState:
        """Post-processing hook - can be overridden"""
        # Update processing duration
        duration = (datetime.now() - start_time).total_seconds()
        
        return {
            **state,
            "processing_duration": {
                **state.get("processing_duration", {}),
                self.node_name.lower(): duration
            }
        }
    
    async def _handle_error(self, state: UnifiedRAGState, error: Exception) -> UnifiedRAGState:
        """Error handling - can be overridden"""
        error_message = f"{self.node_name} error: {str(error)}"
        
        return {
            **state,
            "error_messages": state.get("error_messages", []) + [error_message],
            "processing_status": "failed"
        }
    
    def _update_confidence(self, state: UnifiedRAGState, node_confidence: float) -> Dict[str, float]:
        """Helper to update confidence scores"""
        confidence_scores = state.get("confidence_scores", {})
        confidence_scores[self.node_name.lower()] = node_confidence
        return confidence_scores
    
    def _log_metrics(self, metrics: Dict[str, Any]):
        """Helper to log metrics"""
        logger.info(f"{self.node_name} metrics: {metrics}")


class AnalysisNode(BaseWorkflowNode):
    """Base cho analysis nodes"""
    
    async def _analyze_with_llm(self, prompt: str) -> Dict[str, Any]:
        """Common LLM analysis pattern"""
        from services.llm.provider_manager import llm_provider_manager
        
        enabled_providers = self.settings.get_enabled_providers()
        if not enabled_providers:
            raise ValueError("No LLM providers enabled")
        
        llm = await llm_provider_manager.get_provider(enabled_providers[0])
        response = await llm.ainvoke(prompt)
        
        return await self._parse_llm_response(response.content)
    
    async def _parse_llm_response(self, response_content: str) -> Dict[str, Any]:
        """Parse JSON từ LLM response"""
        import json
        
        json_start = response_content.find('{')
        json_end = response_content.rfind('}') + 1
        
        if json_start >= 0 and json_end > json_start:
            json_str = response_content[json_start:json_end]
            return json.loads(json_str)
        else:
            return self._get_fallback_analysis()
    
    def _get_fallback_analysis(self) -> Dict[str, Any]:
        """Fallback analysis when LLM fails"""
        return {
            "confidence": 0.3,
            "method": "fallback",
            "reasoning": "LLM analysis failed"
        } 