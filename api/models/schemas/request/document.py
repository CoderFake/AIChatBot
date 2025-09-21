from pydantic import BaseModel, Field
from typing import Optional, List
from uuid import UUID

class DocumentUploadRequest(BaseModel):
    """Request model for uploading document"""
    collection_name: str = Field(..., description="Collection name for the document")
    access_level: str = Field(..., description="Access level: public or private")
    folder_id: Optional[str] = Field(None, description="Folder ID to upload to")
    title: Optional[str] = Field(None, description="Document title")
    description: Optional[str] = Field(None, description="Document description")

class FolderCreateRequest(BaseModel):
    """Request model for creating folder"""
    folder_name: str = Field(..., description="Name of the folder")
    parent_folder_id: Optional[str] = Field(None, description="Parent folder ID")
    access_level: Optional[str] = Field("public", description="Access level: public or private")

class FolderUpdateRequest(BaseModel):
    """Request model for updating folder"""
    folder_name: Optional[str] = Field(None, description="New folder name")
    access_level: Optional[str] = Field(None, description="New access level")

class DocumentUpdateRequest(BaseModel):
    """Request model for updating document"""
    title: Optional[str] = Field(None, description="New document title")
    description: Optional[str] = Field(None, description="New document description")
    access_level: Optional[str] = Field(None, description="New access level")

class DocumentMoveRequest(BaseModel):
    """Request model for moving document"""
    target_folder_id: str = Field(..., description="Target folder ID to move to")

class FolderMoveRequest(BaseModel):
    """Request model for moving folder"""
    target_parent_id: str = Field(..., description="Target parent folder ID")
