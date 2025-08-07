from typing import Optional, Dict, Any
from pydantic import BaseModel, Field


class CreateTenantRequest(BaseModel):
    """Request model for creating tenant"""
    tenant_name: str = Field(..., min_length=1, max_length=200)
    timezone: str = Field(default="UTC")
    workflow_provider: Optional[str] = Field(default=None)
    workflow_model: Optional[str] = Field(default=None)


class UpdateTenantRequest(BaseModel):
    """Request model for updating tenant"""
    tenant_name: Optional[str] = Field(None, min_length=1, max_length=200)
    timezone: Optional[str] = Field(None)
    is_active: Optional[bool] = Field(None)


class UpdateWorkflowAgentRequest(BaseModel):
    """Request model for updating WorkflowAgent"""
    provider_name: Optional[str] = Field(None)
    model_name: Optional[str] = Field(None)
    is_active: Optional[bool] = Field(None)
