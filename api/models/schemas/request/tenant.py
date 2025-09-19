from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field


class ProviderConfig(BaseModel):
    """Configuration for provider setup"""
    model_config = {"protected_namespaces": ()}

    provider_name: str = Field(..., description="Provider name (e.g., 'openai', 'anthropic')")
    model_name: str = Field(..., description="Model name for the provider")
    api_keys: Optional[Dict[str, str]] = Field(default=None, description="API keys for the provider")
    provider_model_config: Optional[Dict[str, Any]] = Field(default=None, description="Model configuration")


class CreateTenantRequest(BaseModel):
    """Request model for creating tenant with optional provider and tools setup"""
    tenant_name: str = Field(..., min_length=1, max_length=200)
    timezone: str = Field(..., min_length=1)
    sub_domain: Optional[str] = Field(default=None)
    locale: Optional[str] = Field(default="en_US")
    description: Optional[str] = Field(default=None)
    allowed_providers: Optional[List[str]] = Field(default=None, description="List of provider IDs that tenant can use")
    allowed_tools: Optional[List[str]] = Field(default=None, description="List of tool names to enable for tenant")


class UpdateTenantRequest(BaseModel):
    """Request model for updating tenant"""
    tenant_name: Optional[str] = Field(None, min_length=1, max_length=200)
    timezone: Optional[str] = Field(None)
    is_active: Optional[bool] = Field(None)
    sub_domain: Optional[str] = Field(None)
    locale: Optional[str] = Field(None)
    description: Optional[str] = Field(None)


class UpdateWorkflowAgentRequest(BaseModel):
    """Request model for updating WorkflowAgent"""
    model_config = {"protected_namespaces": ()}

    provider_name: Optional[str] = Field(None)
    model_name: Optional[str] = Field(None)
    is_active: Optional[bool] = Field(None)
