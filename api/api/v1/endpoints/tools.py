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


@router.post("/{tool_id}/departments/{department_id}", summary="Configure tool for a department")
async def configure_tool(
    tool_id: str,
    department_id: str,
    request: ToolConfigRequest,
) -> Dict[str, Any]:
    async with get_db_context() as db:
        service = ToolService(db)
        success = await service.configure_tool_for_department(
            tool_id=tool_id,
            department_id=department_id,
            is_enabled=request.is_enabled,
            config_data=request.config_data or {},
        )
        if not success:
            raise HTTPException(status_code=404, detail="Tool or department not found")
        return {"status": "success"}
