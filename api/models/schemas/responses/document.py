from __future__ import annotations

from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any, Union
from datetime import datetime

class DocumentItemResponse(BaseModel):
    """Response model for individual document"""
    id: str
    filename: str
    title: str
    description: Optional[str]
    file_size: int
    file_type: str
    access_level: str
    processing_status: str
    vector_status: str
    chunk_count: int
    created_at: datetime
    updated_at: Optional[datetime]
    uploaded_by: str
    folder_path: str

class FolderItemResponse(BaseModel):
    """Response model for individual folder"""
    id: str
    folder_name: str
    folder_path: str
    access_level: str
    parent_folder_id: Optional[str]
    document_count: int
    subfolder_count: int
    created_at: datetime
    created_by: Optional[str]

class FolderTreeNode(BaseModel):
    """Tree node for folder structure"""
    id: str
    name: str
    type: str  # "folder" or "document"
    access_level: str
    path: str
    children: List['FolderTreeNode'] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)

class DepartmentTreeResponse(BaseModel):
    """Response model for department folder tree"""
    department_id: str
    department_name: str
    public_tree: FolderTreeNode
    private_tree: FolderTreeNode
    total_documents: int
    total_folders: int

class AdminDocumentTreeResponse(BaseModel):
    """Response model for admin view with all departments"""
    tenant_id: str
    departments: List[DepartmentTreeResponse]
    total_departments: int
    total_documents: int
    total_folders: int

class DocumentTreeResponse(BaseModel):
    """Unified response for document tree based on user role"""
    success: bool
    data: Union[AdminDocumentTreeResponse, DepartmentTreeResponse]
    user_permissions: Dict[str, bool]

class DocumentUploadResponse(BaseModel):
    """Response model for document upload"""
    success: bool
    document_id: str
    filename: str
    bucket: str
    storage_key: str
    collection: str
    access_level: str
    message: str

class FolderCreateResponse(BaseModel):
    """Response model for folder creation"""
    success: bool
    folder_id: str
    folder_name: str
    folder_path: str
    access_level: str
    message: str

class DocumentUpdateResponse(BaseModel):
    """Response model for document/folder update"""
    success: bool
    id: str
    message: str

class DocumentDeleteResponse(BaseModel):
    """Response model for document/folder deletion"""
    success: bool
    id: str
    deleted_count: int
    message: str
    warnings: Optional[List[str]] = None

class DocumentMoveResponse(BaseModel):
    """Response model for document/folder move"""
    success: bool
    id: str
    new_path: str
    message: str

# Forward references are handled automatically with __future__ annotations