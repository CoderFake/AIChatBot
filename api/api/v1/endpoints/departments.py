"""Department management endpoints"""
from typing import Any, Dict, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession

from config.database import get_db
from services.agents.agent_service import AgentService
from api.v1.middleware.middleware import RequireAtLeastAdmin
from models.schemas.responses.tenant import OperationResult

router = APIRouter()


@router.get("", summary="List departments")
async def list_departments(
    tenant_id: Optional[str] = Query(None, description="Filter by tenant ID"),
    db: AsyncSession = Depends(get_db),
    user_ctx: dict = Depends(RequireAtLeastAdmin())
) -> Dict[str, Any]:
    """List departments with optional tenant filtering"""
    try:
        agent_service = AgentService(db)
        departments = await agent_service.get_departments(tenant_id)

        return {
            "departments": departments,
            "total": len(departments)
        }

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list departments: {str(e)}"
        )


@router.get("/{department_id}", summary="Get department details")
async def get_department(
    department_id: str,
    db: AsyncSession = Depends(get_db),
    user_ctx: dict = Depends(RequireAtLeastAdmin())
) -> Dict[str, Any]:
    """Get department details with agents"""
    try:
        agent_service = AgentService(db)
        department = await agent_service.get_department(department_id)

        if not department:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Department not found"
            )

        return {"department": department}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get department: {str(e)}"
        )


@router.put("/{department_id}", summary="Update department")
async def update_department(
    department_id: str,
    department_name: str,
    db: AsyncSession = Depends(get_db),
    user_ctx: dict = Depends(RequireAtLeastAdmin())
) -> OperationResult:
    """Update department name"""
    try:
        agent_service = AgentService(db)
        success = await agent_service.update_department(department_id, department_name)

        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Department not found or update failed"
            )

        return OperationResult(
            success=True,
            message=f"Department updated successfully to '{department_name}'"
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update department: {str(e)}"
        )


@router.delete("/{department_id}", summary="Delete department")
async def delete_department(
    department_id: str,
    cascade: bool = Query(True, description="Delete associated agents"),
    db: AsyncSession = Depends(get_db),
    user_ctx: dict = Depends(RequireAtLeastAdmin())
) -> OperationResult:
    """Delete department and optionally its agents"""
    try:
        agent_service = AgentService(db)
        success = await agent_service.delete_department(department_id, cascade)

        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Department not found or cannot be deleted"
            )

        return OperationResult(
            success=True,
            message=f"Department deleted successfully (cascade={cascade})"
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete department: {str(e)}"
        )


@router.get("/{department_id}/agents", summary="List agents in department")
async def list_department_agents(
    department_id: str,
    db: AsyncSession = Depends(get_db),
    user_ctx: dict = Depends(RequireAtLeastAdmin())
) -> Dict[str, Any]:
    """List all agents in a department"""
    try:
        agent_service = AgentService(db)
        agents = await agent_service.get_agents_by_department(department_id)

        return {
            "agents": list(agents.values()),
            "total": len(agents),
            "department_id": department_id
        }

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list department agents: {str(e)}"
        )
