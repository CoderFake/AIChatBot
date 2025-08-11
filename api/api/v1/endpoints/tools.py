"""Tool management endpoints"""
from typing import Any, Dict, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from config.database import get_db_context
from services.tools.tool_service import ToolService

router = APIRouter()


@router.get("/", summary="List available tools")
async def list_tools() -> Dict[str, Any]:
    async with get_db_context() as db:
        service = ToolService(db)
        tools = await service.get_all_tools()
        return {"tools": tools}


class ToolConfigRequest(BaseModel):
    is_enabled: bool
    config_data: Optional[Dict[str, Any]] = None


@router.post("/{tool_id}/tenants/{tenant_id}", summary="Configure tool for a tenant")
async def configure_tool_for_tenant(
    tool_id: str,
    tenant_id: str,
    request: ToolConfigRequest,
) -> Dict[str, Any]:
    async with get_db_context() as db:
        service = ToolService(db)
        success = await service.configure_tool_for_tenant(
            tool_id=tool_id,
            tenant_id=tenant_id,
            is_enabled=request.is_enabled,
            config_data=request.config_data or {},
        )
        if not success:
            raise HTTPException(status_code=404, detail="Tool or tenant not found")
        return {"status": "success"}


@router.get("/tenants/{tenant_id}", summary="List tools for a tenant")
async def list_tenant_tools(tenant_id: str) -> Dict[str, Any]:
    async with get_db_context() as db:
        service = ToolService(db)
        tools = await service.get_tenant_tools(tenant_id)
        return {"tools": tools}
