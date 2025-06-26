from pydantic import BaseModel, Field
from typing import Optional

class DocumentSearchRequest(BaseModel):
    """Request model cho document search"""
    query: str = Field(..., description="Query để tìm kiếm")
    top_k: Optional[int] = Field(5, description="Số lượng kết quả trả về", ge=1, le=50)
    threshold: Optional[float] = Field(0.3, description="Ngưỡng similarity", ge=0.0, le=1.0)
    department: Optional[str] = Field(None, description="Filter theo phòng ban")
    document_type: Optional[str] = Field(None, description="Filter theo loại tài liệu")

