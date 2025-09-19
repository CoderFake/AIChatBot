"""Tool management endpoints with role-based access"""
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
from models.schemas.request.tool import ToolConfigRequest

router = APIRouter()

@router.get("/available", summary="List tools based on user role and context")
async def list_tools_by_role(
    tenant_id: Optional[str] = None,
    department_id: Optional[str] = None,
    user_ctx: dict = Depends(RequireAtLeastDeptAdmin()),
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """
    List tools depending on role and context:
    - MAINTAINER: All tools with tenant configs
    - ADMIN: Tools of tenant 
    - DEPT_ADMIN: Tools of department
    - USER: Tools that can be used
    """
    try:
        validator = ValidatePermission(db)
        
        user_role = user_ctx.get("role")
        user_id = user_ctx.get("user_id")
        
        if not tenant_id and "tenant_id" in user_ctx:
            tenant_id = user_ctx.get("tenant_id")
        if not department_id and "department_id" in user_ctx:
            department_id = user_ctx.get("department_id")
        
        result = await validator.get_tools_by_role_context(
            user_role=user_role,
            tenant_id=tenant_id,
            department_id=department_id,
            user_id=user_id
        )
        
        return result
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{tool_id}/tenants/{tenant_id}", summary="Configure tool for tenant")
async def configure_tool_for_tenant(
    tool_id: str,
    tenant_id: str,
    request: ToolConfigRequest,
    admin: dict = Depends(RequireAtLeastAdmin()),
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """Configure tool for tenant (ADMIN level allows configuring any tenant)"""
    try:
        validator = ValidatePermission(db)
        user_role = admin.get("role")
        
        if user_role != "MAINTAINER":
            admin_tenant_id = admin.get("tenant_id")
            if admin_tenant_id != tenant_id:
                raise HTTPException(
                    status_code=403,
                    detail="Admin can only configure tools for their own tenant"
                )
        
        from services.tools.tool_service import ToolService
        service = ToolService(db)
        
        success = await service.configure_tool_for_tenant(
            tool_id=tool_id,
            tenant_id=tenant_id,
            is_enabled=request.is_enabled,
            config_data=request.config_data or {},
        )
        
        if not success:
            raise HTTPException(status_code=404, detail="Tool or tenant not found")
        
        return {"status": "success", "tool_id": tool_id, "tenant_id": tenant_id}
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/tenants/{tenant_id}", summary="List tools for specific tenant")
async def list_tenant_tools(
    tenant_id: str,
    admin: dict = Depends(RequireAtLeastAdmin()),
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """List tools for specific tenant (ADMIN of tenant or MAINTAINER)""" 
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
        result = await validator.get_tools_by_role_context(
            user_role=user_role,
            tenant_id=tenant_id,
            department_id=None,
            user_id=admin.get("user_id")
        )
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ==================== MAINTAINER-ONLY ENDPOINTS ====================

@router.post("/maintainer", summary="Create new tool (MAINTAINER only)")
async def maintainer_create_tool(
    request: dict,
    maintainer: dict = Depends(RequireOnlyMaintainer()),
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """Create new tool (MAINTAINER only)"""
    try:
        from services.tools.tool_service import ToolService
        service = ToolService(db)
        
        tool_data = await service.create_tool(
            tool_name=request.get("tool_name"),
            description=request.get("description"),
            tool_type=request.get("tool_type"),
            config_schema=request.get("config_schema", {}),
            is_system=request.get("is_system", False)
        )
        
        return {"tool": tool_data, "status": "created"}
        
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.put("/maintainer/{tool_id}", summary="Update tool (MAINTAINER only)")
async def maintainer_update_tool(
    tool_id: str,
    request: dict,
    maintainer: dict = Depends(RequireOnlyMaintainer()),
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """Update tool (MAINTAINER only)"""
    try:
        from services.tools.tool_service import ToolService
        service = ToolService(db)
        
        success = await service.update_tool(tool_id, request)
        if not success:
            raise HTTPException(status_code=404, detail="Tool not found")
            
        return {"status": "updated", "tool_id": tool_id}
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/maintainer/{tool_id}", summary="Delete tool (MAINTAINER only)")
async def maintainer_delete_tool(
    tool_id: str,
    maintainer: dict = Depends(RequireOnlyMaintainer()),
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """Delete tool (MAINTAINER only)"""
    try:
        from services.tools.tool_service import ToolService
        service = ToolService(db)
        
        success = await service.delete_tool(tool_id)
        if not success:
            raise HTTPException(status_code=404, detail="Tool not found")
            
        return {"status": "deleted", "tool_id": tool_id}
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/maintainer/{tool_id}/tenants/{tenant_id}/enable", summary="Enable tool for tenant (MAINTAINER)")
async def maintainer_enable_tool_for_tenant(
    tool_id: str,
    tenant_id: str,
    request: ToolConfigRequest,
    maintainer: dict = Depends(RequireOnlyMaintainer()),
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """Enable tool for specific tenant (MAINTAINER only)"""
    try:
        from services.tools.tool_service import ToolService
        service = ToolService(db)
        
        success = await service.configure_tool_for_tenant(
            tool_id=tool_id,
            tenant_id=tenant_id,
            is_enabled=request.is_enabled,
            config_data=request.config_data or {}
        )
        
        if not success:
            raise HTTPException(status_code=404, detail="Tool or tenant not found")
            
        return {"status": "success", "tool_id": tool_id, "tenant_id": tenant_id}
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/maintainer/{tool_id}/tenants/{tenant_id}", summary="Remove tool from tenant (MAINTAINER)")
async def maintainer_remove_tool_from_tenant(
    tool_id: str,
    tenant_id: str,
    maintainer: dict = Depends(RequireOnlyMaintainer()),
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """Remove tool from tenant (MAINTAINER only)"""
    try:
        from services.tools.tool_service import ToolService
        service = ToolService(db)
        
        success = await service.remove_tool_from_tenant(tool_id, tenant_id)
        if not success:
            raise HTTPException(status_code=404, detail="Tool configuration not found")
            
        return {"status": "removed", "tool_id": tool_id, "tenant_id": tenant_id}
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))