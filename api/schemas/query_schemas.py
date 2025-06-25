from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field


class QueryRequest(BaseModel):
    """RAG query request model"""
    query: str = Field(..., description="User query", max_length=1000)
    language: str = Field(default="vi", description="Query language")
    user_id: Optional[str] = Field(None, description="User ID")
    session_id: Optional[str] = Field(None, description="Session ID")
    conversation_history: List[Dict[str, Any]] = Field(default=[], description="Previous conversation")

class QueryResponse(BaseModel):
    """RAG query response model"""
    response: str = Field(..., description="Generated response")
    sources: List[str] = Field(default=[], description="Document sources")
    confidence: float = Field(..., description="Response confidence score")
    workflow_id: str = Field(..., description="Workflow execution ID")
    processing_time: float = Field(..., description="Processing time in seconds")
    metadata: Dict[str, Any] = Field(default={}, description="Additional metadata")

class HealthResponse(BaseModel):
    """System health response model"""
    status: str = Field(..., description="Overall system status")
    components: Dict[str, Dict[str, Any]] = Field(..., description="Component health details")
    timestamp: str = Field(..., description="Health check timestamp")
