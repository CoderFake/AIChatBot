from typing import Optional, List, Dict, Any
from pydantic import BaseModel


class TenantResponse(BaseModel):
    id: str
    tenant_name: str
    timezone: str
    locale: str
    sub_domain: Optional[str]
    is_active: bool
    description: Optional[str] = None
    created_at: str
    updated_at: str


class TenantListResponse(BaseModel):
    tenants: List[TenantResponse]
    total: int
    page: int
    limit: int
    has_more: bool

class CreateTenantResponse(BaseModel):
    tenant_id: str
    tenant_name: str
    timezone: str
    locale: str
    sub_domain: Optional[str]
    description: Optional[str] = None
    default_groups: Dict[str, str]
    created_at: str

class OperationResult(BaseModel):
    success: bool
    detail: Optional[str] = None


