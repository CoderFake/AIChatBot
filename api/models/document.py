from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field

class DocumentMetadata(BaseModel):
    """Metadata cho document"""
    title: Optional[str] = Field(None, description="Tiêu đề tài liệu")
    author: Optional[str] = Field(None, description="Tác giả")
    department: Optional[str] = Field(None, description="Phòng ban liên quan")
    tags: List[str] = Field(default=[], description="Tags cho classification")
    description: Optional[str] = Field(None, description="Mô tả tài liệu")
    language: Optional[str] = Field("vi", description="Ngôn ngữ của tài liệu")

