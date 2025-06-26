from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any

class DocumentResponse(BaseModel):
    """Response model cho document operations"""
    document_id: str = Field(..., description="ID của document")
    filename: str = Field(..., description="Tên file")
    status: str = Field(..., description="Trạng thái xử lý")
    message: str = Field(..., description="Thông báo")
    processing_time: Optional[float] = Field(None, description="Thời gian xử lý")
    chunk_count: Optional[int] = Field(None, description="Số lượng chunks được tạo")
    error: Optional[str] = Field(None, description="Lỗi nếu có")


class DocumentSearchResponse(BaseModel):
    """Response model cho document search"""
    query: str = Field(..., description="Query đã search")
    results: List[Dict[str, Any]] = Field(..., description="Kết quả tìm kiếm")
    total_found: int = Field(..., description="Tổng số kết quả")
    processing_time: float = Field(..., description="Thời gian xử lý")


class DocumentStatusResponse(BaseModel):
    """Response model cho document status"""
    document_id: str = Field(..., description="ID của document")
    status: str = Field(..., description="Trạng thái: processing, completed, failed")
    processing_progress: int = Field(..., description="Tiến độ xử lý (%)")
    chunk_count: Optional[int] = Field(None, description="Số lượng chunks")
    created_at: str = Field(..., description="Thời gian tạo")
    processed_at: Optional[str] = Field(None, description="Thời gian hoàn thành")
    error: Optional[str] = Field(None, description="Lỗi nếu có")


class DocumentListItem(BaseModel):
    """Model cho document trong list"""
    document_id: str = Field(..., description="ID của document")
    filename: str = Field(..., description="Tên file")
    title: str = Field(..., description="Tiêu đề")
    author: Optional[str] = Field(None, description="Tác giả")
    department: Optional[str] = Field(None, description="Phòng ban")
    status: str = Field(..., description="Trạng thái")
    chunk_count: int = Field(..., description="Số lượng chunks")
    created_at: str = Field(..., description="Thời gian tạo")
    tags: List[str] = Field(default=[], description="Tags")


class DocumentListResponse(BaseModel):
    """Response model cho document list"""
    documents: List[DocumentListItem] = Field(..., description="Danh sách documents")
    pagination: Dict[str, Any] = Field(..., description="Thông tin pagination")
    filters: Dict[str, Any] = Field(..., description="Filters đã áp dụng")


class DocumentStatsResponse(BaseModel):
    """Response model cho document statistics"""
    total_documents: int = Field(..., description="Tổng số documents")
    processed_documents: int = Field(..., description="Số documents đã xử lý")
    processing_documents: int = Field(..., description="Số documents đang xử lý")
    failed_documents: int = Field(..., description="Số documents lỗi")
    total_chunks: int = Field(..., description="Tổng số chunks")
    storage_used_mb: float = Field(..., description="Dung lượng sử dụng (MB)")
    by_department: Dict[str, int] = Field(..., description="Phân bố theo phòng ban")
    by_type: Dict[str, int] = Field(..., description="Phân bố theo loại file")
    processing_queue: Dict[str, int] = Field(..., description="Trạng thái queue")
    last_updated: str = Field(..., description="Thời gian cập nhật cuối")


class DocumentDeleteResponse(BaseModel):
    """Response model cho document deletion"""
    document_id: str = Field(..., description="ID của document")
    status: str = Field(..., description="Trạng thái deletion")
    message: str = Field(..., description="Thông báo")


class DocumentReprocessResponse(BaseModel):
    """Response model cho document reprocessing"""
    document_id: str = Field(..., description="ID của document")
    status: str = Field(..., description="Trạng thái reprocessing")
    message: str = Field(..., description="Thông báo") 