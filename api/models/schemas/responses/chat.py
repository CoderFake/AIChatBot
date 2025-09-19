
"""
Chat response schemas for different event types
"""
from typing import List, Optional, Dict, Any, Literal
from pydantic import BaseModel, Field


class ChatProgressEvent(BaseModel):
    """Progress event during chat processing"""
    type: Literal["start", "progress", "planning", "execution", "resolution", "final_result", "error", "complete"]
    node: Optional[str] = Field(None, description="Current workflow node")
    progress: int = Field(0, description="Progress percentage 0-100")
    status: str = Field("processing", description="Current status")
    message: str = Field("", description="Progress message")


class PlanningEvent(ChatProgressEvent):
    """Planning phase event with semantic routing data"""
    type: Literal["planning"] = "planning"
    planning_data: Optional[Dict[str, Any]] = Field(None, description="Semantic routing and execution plan")


class ExecutionEvent(ChatProgressEvent):
    """Execution phase event with step results"""
    type: Literal["execution"] = "execution"
    execution_data: Optional[Dict[str, Any]] = Field(None, description="Current step results and agent responses")


class ResolutionEvent(ChatProgressEvent):
    """Conflict resolution event"""
    type: Literal["resolution"] = "resolution"
    resolution_data: Optional[Dict[str, Any]] = Field(None, description="Conflict resolution results")


class FinalResultEvent(ChatProgressEvent):
    """Final result event"""
    type: Literal["final_result"] = "final_result"
    final_data: Optional[Dict[str, Any]] = Field(None, description="Final response and sources")


class ErrorEvent(ChatProgressEvent):
    """Error event"""
    type: Literal["error"] = "error"
    error_data: Optional[Dict[str, Any]] = Field(None, description="Error information")