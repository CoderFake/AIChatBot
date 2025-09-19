"""Provider management endpoints with role-based access"""
from typing import Any, Dict, Optional
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from config.database import get_db
from services.auth.validate_permission import ValidatePermission
from api.v1.middleware.middleware import (
    RequireAtLeastAdmin, 
    RequireOnlyMaintainer,
    RequireAtLeastDeptAdmin
)
from models.schemas.request.provider import ProviderConfigRequest

router = APIRouter()


@router.get("/", summary="List providers based on user role and context")
async def list_providers_by_role(
    tenant_id: Optional[str] = None,
    department_id: Optional[str] = None,
    user_ctx: dict = Depends(RequireAtLeastDeptAdmin()),
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """
    List providers depending on role and context:
    - MAINTAINER: All providers with tenant configs
    - ADMIN: Providers of tenant with config access
    - DEPT_ADMIN+: Providers enabled for tenant (read-only)
    """
    try:
        validator = ValidatePermission(db)
        
        user_role = user_ctx.get("role")
        
        if not tenant_id and "tenant_id" in user_ctx:
            tenant_id = user_ctx.get("tenant_id")
        if not department_id and "department_id" in user_ctx:
            department_id = user_ctx.get("department_id")
        
        result = await validator.get_providers_by_role_context(
            user_role=user_role,
            tenant_id=tenant_id,
            department_id=department_id
        )
        
        return result
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/available", summary="Get available providers for tenant setup (MAINTAINER only)")
async def get_available_providers_for_setup(
    maintainer: dict = Depends(RequireOnlyMaintainer()),
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """Endpoint for MAINTAINER to create tenant - list all providers available"""
    try:
        validator = ValidatePermission(db)
        
        result = await validator.get_providers_by_role_context(
            user_role=maintainer.get("role"),
            tenant_id=None,
            department_id=None
        )
        
        formatted_providers = []
        for provider in result.get("providers", []):
            formatted_providers.append({
                "id": provider.get("id"),
                "name": provider.get("provider_name"),
                "description": provider.get("description"),
                "type": provider.get("provider_type"),
                "is_enabled": provider.get("is_enabled", True)
            })
        
        return {"providers": formatted_providers}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{provider_id}/tenants/{tenant_id}", summary="Configure provider for tenant")
async def configure_provider_for_tenant(
    provider_id: str,
    tenant_id: str,
    request: ProviderConfigRequest,
    admin: dict = Depends(RequireAtLeastAdmin()),
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """Configure provider for tenant (ADMIN level or higher)""" 
    try:
        user_role = admin.get("role")
        
        if user_role != "MAINTAINER":
            admin_tenant_id = admin.get("tenant_id")
            if admin_tenant_id != tenant_id:
                raise HTTPException(
                    status_code=403,
                    detail="Admin can only configure providers for their own tenant"
                )
        
        from services.llm.provider_service import ProviderService
        service = ProviderService(db)
        
        success = await service.configure_tenant_provider(
            provider_id=provider_id,
            tenant_id=tenant_id,
            is_enabled=request.is_enabled,
            api_keys=request.api_keys or {},
            provider_config=request.provider_config or {}
        )
        
        if not success:
            raise HTTPException(status_code=404, detail="Provider or tenant not found")
        
        return {"status": "success", "provider_id": provider_id, "tenant_id": tenant_id}
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/tenants/{tenant_id}", summary="List providers for specific tenant")
async def list_tenant_providers(
    tenant_id: str,
    admin: dict = Depends(RequireAtLeastAdmin()),
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """List providers for specific tenant (ADMIN of tenant or MAINTAINER)""" 
    try:
        user_role = admin.get("role")
        if user_role != "MAINTAINER":
            admin_tenant_id = admin.get("tenant_id")
            if admin_tenant_id != tenant_id:
                raise HTTPException(
                    status_code=403,
                    detail="Access denied for this tenant"
                )
        
        validator = ValidatePermission(db)
        result = await validator.get_providers_by_role_context(
            user_role=user_role,
            tenant_id=tenant_id,
            department_id=None
        )
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{provider_id}/models", summary="Get available models for provider")
async def get_provider_models(
    provider_id: str,
    user_ctx: dict = Depends(RequireAtLeastDeptAdmin()),
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """Get available models for provider (any authenticated user)"""
    try:
        from services.llm.provider_service import ProviderService
        service = ProviderService(db)
        
        models = await service.get_provider_models(provider_id)
        return {"models": models, "provider_id": provider_id}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/maintainer/{provider_id}", summary="Update provider (MAINTAINER only)")
async def maintainer_update_provider(
    provider_id: str,
    request: dict,
    maintainer: dict = Depends(RequireOnlyMaintainer()),
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """Update provider (MAINTAINER only)"""
    try:
        from services.llm.provider_service import ProviderService
        service = ProviderService(db)
        
        success = await service.update_provider(provider_id, request)
        if not success:
            raise HTTPException(status_code=404, detail="Provider not found")
            
        return {"status": "updated", "provider_id": provider_id}
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/maintainer/{provider_id}/tenants/{tenant_id}/enable", summary="Enable provider for tenant (MAINTAINER)")
async def maintainer_enable_provider_for_tenant(
    provider_id: str,
    tenant_id: str,
    request: ProviderConfigRequest,
    maintainer: dict = Depends(RequireOnlyMaintainer()),
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """Enable provider for specific tenant (MAINTAINER only)"""
    try:
        from services.llm.provider_service import ProviderService
        service = ProviderService(db)
        
        success = await service.configure_tenant_provider(
            provider_id=provider_id,
            tenant_id=tenant_id,
            is_enabled=request.is_enabled,
            api_keys=request.api_keys or {},
            provider_config=request.provider_config or {}
        )
        
        if not success:
            raise HTTPException(status_code=404, detail="Provider or tenant not found")
            
        return {"status": "success", "provider_id": provider_id, "tenant_id": tenant_id}
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/maintainer/{provider_id}/tenants/{tenant_id}", summary="Remove provider from tenant (MAINTAINER)")
async def maintainer_remove_provider_from_tenant(
    provider_id: str,
    tenant_id: str,
    maintainer: dict = Depends(RequireOnlyMaintainer()),
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """Remove provider from tenant (MAINTAINER only)"""
    try:
        from services.llm.provider_service import ProviderService
        service = ProviderService(db)
        
        success = await service.remove_provider_from_tenant(provider_id, tenant_id)
        if not success:
            raise HTTPException(status_code=404, detail="Provider configuration not found")
            
        return {"status": "removed", "provider_id": provider_id, "tenant_id": tenant_id}
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))