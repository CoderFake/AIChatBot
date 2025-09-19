
"""
Updated chat request schemas
"""
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class ChatMessage(BaseModel):
    """Single chat message"""
    role: str = Field(..., description="Message role: user, assistant")
    content: str = Field(..., description="Message content")
    timestamp: Optional[str] = Field(None, description="Message timestamp")


class AccessScope(BaseModel):
    """Access scope configuration"""
    visibility: str = Field(..., description="Access visibility: 'public', 'private', or 'both'")

class ChatRequest(BaseModel):
    """Chat query request"""
    query: str = Field(..., description="User query")
    session_id: Optional[str] = Field(None, description="Session ID for tracking")
    access_scope: Optional[AccessScope] = Field(
        None,
        description="Override access scope configuration. If not provided, uses user's default permissions"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "query": "giá trị cốt lõi, muộn có ảnh hưởng đến giá trị nào không",
                "session_id": "session_123",
                "access_scope": "private"
            }
        }

