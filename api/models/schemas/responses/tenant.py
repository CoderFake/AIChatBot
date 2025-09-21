from typing import Optional, List, Dict, Any
from pydantic import BaseModel


class TenantResponse(BaseModel):
    """Basic tenant information used in list views."""
    id: str
    tenant_name: str
    timezone: str
    locale: str
    sub_domain: Optional[str]
    is_active: bool
    description: Optional[str] = None
    created_at: str
    updated_at: str


class CompanyInfo(BaseModel):
    """Company profile information for a tenant."""
    address: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None


class Branding(BaseModel):
    """Branding configuration for a tenant."""
    logo_url: Optional[str] = None
    primary_color: Optional[str] = None


class ChatbotSettings(BaseModel):
    """Chatbot configuration for a tenant."""
    name: Optional[str] = None
    description: Optional[str] = None


class TenantSettings(BaseModel):
    """Aggregated settings for a tenant, used in detail responses."""
    description: Optional[str] = None
    company_info: Optional[CompanyInfo] = None
    branding: Optional[Branding] = None
    chatbot: Optional[ChatbotSettings] = None


class TenantDetailResponse(TenantResponse):
    """Full tenant detail information including nested settings and counters."""
    tenant_id: str
    status: Optional[str] = None
    settings: Optional[TenantSettings] = None
    admin_count: Optional[int] = None
    user_count: Optional[int] = None
    is_deleted: Optional[bool] = None
    deleted_at: Optional[str] = None
    version: Optional[str] = None


class TenantListResponse(BaseModel):
    """Paginated list response for tenants."""
    tenants: List[TenantResponse]
    total: int
    page: int
    limit: int
    has_more: bool


class CreateTenantResponse(BaseModel):
    """Response body for successful tenant creation."""
    tenant_id: str
    tenant_name: str
    timezone: str
    locale: str
    sub_domain: Optional[str]
    description: Optional[str] = None
    default_groups: Dict[str, str]
    created_at: str
    setup_results: Optional[Dict[str, Any]] = None


class PublicTenantResponse(BaseModel):
    """Public tenant information for organization listing."""
    id: str
    tenant_name: str
    timezone: str
    locale: str
    sub_domain: Optional[str]
    description: Optional[str] = None
    created_at: str
    updated_at: str
    chatbot_name: Optional[str] = None
    chatbot_description: Optional[str] = None
    is_active: bool
    user_count: Optional[int] = None
    department_count: Optional[int] = None


class PublicTenantListResponse(BaseModel):
    """Paginated public tenant list response."""
    tenants: List[PublicTenantResponse]
    total: int
    page: int
    limit: int
    has_more: bool


class TenantPublicInfoResponse(BaseModel):
    """Public tenant information for login pages (no authentication required)."""
    id: str
    tenant_name: str
    locale: str
    is_active: bool
    description: Optional[str] = None
    sub_domain: Optional[str] = None
    logo_url: Optional[str] = None
    primary_color: Optional[str] = None


class UpdateTenantResponse(BaseModel):
    """Response body for successful tenant update."""
    tenant_id: str
    tenant_name: Optional[str] = None
    timezone: Optional[str] = None
    locale: Optional[str] = None
    sub_domain: Optional[str] = None
    description: Optional[str] = None
    updated_at: Optional[str] = None
    setup_results: Optional[Dict[str, Any]] = None


class OperationResult(BaseModel):
    """Generic operation result schema with optional detail message."""
    success: bool
    detail: Optional[str] = None


class TenantSettingsResponse(BaseModel):
    tenant_name: str
    description: Optional[str]
    timezone: str
    locale: str
    chatbot_name: Optional[str] 
    logo_url: Optional[str]      
    bot_name: Optional[str]      
    branding: Optional[Dict[str, Any]] 


