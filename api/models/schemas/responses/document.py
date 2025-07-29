from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any

class DocumentResponse(BaseModel):
    """Response model cho document operations"""
    pass


class DocumentStatusResponse(BaseModel):
    """Response model for document status form kafka"""
    pass


class DocumentDetailResponse(BaseModel):
    """Model of document in list"""
    pass

class DocumentListResponse(BaseModel):
    """
    Response model for document list
    multiple DocumentDetailResponse
    """
    pass


class DocumentStatsResponse(BaseModel):
    """Response model for document statistics""" 
    pass


class DocumentDeleteResponse(BaseModel):
    """Response model for document deletion"""
    pass


class DocumentReprocessResponse(BaseModel):
    """Response model for document reprocessing"""
    pass