from pydantic import BaseModel, Field
from typing import List

class RAGSearchInput(BaseModel):
    """Input schema for RAG search tool"""
    query: str = Field(description="Search query for document retrieval")
    department: str = Field(description="User's department for access control")
    user_id: str = Field(description="User ID for permission checking")
    access_levels: List[str] = Field(
        default=["public"], 
        description="Access levels for search (public, private, etc.)"
    )