"""Agent management endpoints for MAINTAINER and tenant admins"""
from typing import Any, Dict, Optional, List
from fastapi import APIRouter, HTTPException, Depends, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from config.database import get_db
from services.llm.provider_service import ProviderService
from api.v1.middleware.middleware import RequireOnlyMaintainer, RequireAtLeastAdmin
from models.schemas.responses.tenant import OperationResult

router = APIRouter()


class CreateAgentRequest(BaseModel):
    agent_name: str
    provider_id: str
    model_name: str
    description: Optional[str] = None
    config: Optional[Dict[str, Any]] = None


class UpdateAgentRequest(BaseModel):
    agent_name: Optional[str] = None
    provider_id: Optional[str] = None
    model_name: Optional[str] = None
    description: Optional[str] = None
    config: Optional[Dict[str, Any]] = None


class AgentResponse(BaseModel):
    id: str
    agent_name: str
    provider_id: str
    model_name: str
    description: Optional[str] = None
    config: Optional[Dict[str, Any]] = None
    is_active: bool
    tenant_id: Optional[str] = None
    created_at: str
    updated_at: str


@router.get("/", summary="List all agents (MAINTAINER only)")
async def list_agents(
    db: AsyncSession = Depends(get_db),
    maintainer: dict = Depends(RequireOnlyMaintainer())
) -> Dict[str, Any]:
    """List all agents across all tenants (MAINTAINER only)"""
    try:
        from services.llm.provider_service import ProviderService
        provider_service = ProviderService(db)
        agents = await provider_service.get_all_agents()
        return {"agents": agents, "total": len(agents)}
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.get("/{agent_id}", summary="Get agent details")
async def get_agent(
    agent_id: str,
    db: AsyncSession = Depends(get_db),
    user_ctx: dict = Depends(RequireAtLeastAdmin())
) -> AgentResponse:
    """Get agent details"""
    try:
        from services.llm.provider_service import ProviderService
        provider_service = ProviderService(db)
        agent = await provider_service.get_agent_by_id(agent_id)
        if not agent:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")
        return AgentResponse(**agent)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.put("/{agent_id}", summary="Update agent")
async def update_agent(
    agent_id: str,
    request: UpdateAgentRequest,
    db: AsyncSession = Depends(get_db),
    user_ctx: dict = Depends(RequireAtLeastAdmin())
) -> OperationResult:
    """Update agent configuration"""
    try:
        from services.llm.provider_service import ProviderService
        provider_service = ProviderService(db)
        success = await provider_service.update_agent(
            agent_id=agent_id,
            agent_name=request.agent_name,
            provider_id=request.provider_id,
            model_name=request.model_name,
            description=request.description,
            config=request.config
        )
        if not success:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found or update failed")

        return OperationResult(success=True, message="Agent updated successfully")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.delete("/{agent_id}", summary="Delete agent (MAINTAINER only)")
async def delete_agent(
    agent_id: str,
    db: AsyncSession = Depends(get_db),
    maintainer: dict = Depends(RequireOnlyMaintainer())
) -> OperationResult:
    """Delete agent and cascade delete related configurations (MAINTAINER only)"""
    try:
        from services.llm.provider_service import ProviderService
        provider_service = ProviderService(db)
        success = await provider_service.delete_agent_cascade(agent_id)
        if not success:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")

        return OperationResult(success=True, message="Agent deleted successfully with cascade")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.post("/{agent_id}/tenants/{tenant_id}", summary="Assign agent to tenant")
async def assign_agent_to_tenant(
    agent_id: str,
    tenant_id: str,
    db: AsyncSession = Depends(get_db),
    user_ctx: dict = Depends(RequireAtLeastAdmin())
) -> OperationResult:
    """Assign agent to a tenant"""
    try:
        from services.llm.provider_service import ProviderService
        provider_service = ProviderService(db)
        success = await provider_service.assign_agent_to_tenant(agent_id, tenant_id)
        if not success:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Failed to assign agent to tenant")

        return OperationResult(success=True, message="Agent assigned to tenant successfully")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.delete("/{agent_id}/tenants/{tenant_id}", summary="Remove agent from tenant")
async def remove_agent_from_tenant(
    agent_id: str,
    tenant_id: str,
    db: AsyncSession = Depends(get_db),
    user_ctx: dict = Depends(RequireAtLeastAdmin())
) -> OperationResult:
    """Remove agent from a tenant"""
    try:
        from services.llm.provider_service import ProviderService
        provider_service = ProviderService(db)
        success = await provider_service.remove_agent_from_tenant(agent_id, tenant_id)
        if not success:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Failed to remove agent from tenant")

        return OperationResult(success=True, message="Agent removed from tenant successfully")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.get("/tenants/{tenant_id}", summary="List agents for tenant")
async def list_tenant_agents(
    tenant_id: str,
    db: AsyncSession = Depends(get_db),
    user_ctx: dict = Depends(RequireAtLeastAdmin())
) -> Dict[str, Any]:
    """List agents assigned to a tenant"""
    try:
        from services.llm.provider_service import ProviderService
        provider_service = ProviderService(db)
        agents = await provider_service.get_tenant_agents(tenant_id)
        return {"agents": agents, "total": len(agents)}
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))
