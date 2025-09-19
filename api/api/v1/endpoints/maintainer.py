"""Maintainer-only endpoints for system-wide operations"""
from typing import Any, Dict, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from config.database import get_db
from api.v1.middleware.middleware import RequireOnlyMaintainer

router = APIRouter(prefix="/maintainer", tags=["Maintainer"])


@router.get("/stats", summary="Get system-wide statistics (MAINTAINER only)")
async def get_system_stats(
    db: AsyncSession = Depends(get_db),
    maintainer: dict = Depends(RequireOnlyMaintainer())
) -> Dict[str, Any]:
    """Get comprehensive system statistics (MAINTAINER only)"""
    try:
        from models.database.tenant import Tenant
        from models.database.user import User
        from models.database.agent import Agent
        from models.database.tool import Tool

        tenant_result = await db.execute(select(func.count(Tenant.id)))
        total_tenants = tenant_result.scalar() or 0

        # Count users
        user_result = await db.execute(select(func.count(User.id)))
        total_users = user_result.scalar() or 0

        # Count agents
        agent_result = await db.execute(select(func.count(Agent.id)))
        total_agents = agent_result.scalar() or 0

        # Count tools
        tool_result = await db.execute(select(func.count(Tool.id)))
        total_tools = tool_result.scalar() or 0

        active_sessions = 0 

        system_health = "healthy"
        if total_tenants == 0 or total_users == 0:
            system_health = "warning"
        elif total_agents == 0 or total_tools == 0:
            system_health = "warning"

        return {
            "total_tenants": total_tenants,
            "total_users": total_users,
            "total_agents": total_agents,
            "total_tools": total_tools,
            "active_sessions": active_sessions,
            "system_health": system_health,
            "timestamp": "2024-01-01T00:00:00Z"
        }

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get system stats: {str(e)}"
        )


@router.get("/audit-logs", summary="Get audit logs (MAINTAINER only)")
async def get_audit_logs(
    tenant_id: Optional[str] = Query(None, description="Filter by tenant ID"),
    user_id: Optional[str] = Query(None, description="Filter by user ID"),
    action: Optional[str] = Query(None, description="Filter by action type"),
    limit: int = Query(50, ge=1, le=1000, description="Number of records to return"),
    offset: int = Query(0, ge=0, description="Number of records to skip"),
    db: AsyncSession = Depends(get_db),
    maintainer: dict = Depends(RequireOnlyMaintainer())
) -> Dict[str, Any]:
    """Get audit logs with filtering (MAINTAINER only)"""
    try:
        # In a real implementation, you'd have an AuditLog model
        # For now, return mock data structure

        mock_logs = [
            {
                "id": "audit-001",
                "timestamp": "2024-01-01T10:00:00Z",
                "user_id": "user-123",
                "user_email": "admin@tenant1.com",
                "tenant_id": "tenant-1",
                "tenant_name": "Tenant One",
                "action": "CREATE_TENANT",
                "resource_type": "tenant",
                "resource_id": "tenant-1",
                "details": {"tenant_name": "Tenant One"},
                "ip_address": "192.168.1.100",
                "user_agent": "Mozilla/5.0..."
            },
            {
                "id": "audit-002",
                "timestamp": "2024-01-01T11:00:00Z",
                "user_id": "user-456",
                "user_email": "maintainer@system.com",
                "tenant_id": None,
                "tenant_name": None,
                "action": "DELETE_TOOL",
                "resource_type": "tool",
                "resource_id": "tool-123",
                "details": {"tool_name": "Calculator Tool"},
                "ip_address": "192.168.1.101",
                "user_agent": "Mozilla/5.0..."
            }
        ]

        filtered_logs = mock_logs

        if tenant_id:
            filtered_logs = [log for log in filtered_logs if log["tenant_id"] == tenant_id]

        if user_id:
            filtered_logs = [log for log in filtered_logs if log["user_id"] == user_id]

        if action:
            filtered_logs = [log for log in filtered_logs if log["action"] == action]

        # Apply pagination
        paginated_logs = filtered_logs[offset:offset + limit]

        return {
            "logs": paginated_logs,
            "total": len(filtered_logs),
            "limit": limit,
            "offset": offset
        }

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get audit logs: {str(e)}"
        )


@router.get("/tenants/{tenant_id}/usage", summary="Get tenant usage statistics (MAINTAINER only)")
async def get_tenant_usage(
    tenant_id: str,
    db: AsyncSession = Depends(get_db),
    maintainer: dict = Depends(RequireOnlyMaintainer())
) -> Dict[str, Any]:
    """Get detailed usage statistics for a specific tenant (MAINTAINER only)"""
    try:
        from models.database.tenant import Tenant, Department
        from models.database.user import User
        from models.database.agent import Agent
        from models.database.tool import TenantToolConfig

        # Verify tenant exists
        tenant_result = await db.execute(select(Tenant).where(Tenant.id == tenant_id))
        tenant = tenant_result.scalar_one_or_none()

        if not tenant:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found")

        # Count users in tenant
        user_result = await db.execute(select(func.count(User.id)).where(User.tenant_id == tenant_id))
        user_count = user_result.scalar() or 0

        # Count departments
        dept_result = await db.execute(select(func.count(Department.id)).where(Department.tenant_id == tenant_id))
        dept_count = dept_result.scalar() or 0

        # Count agents
        agent_result = await db.execute(select(func.count(Agent.id)).where(Agent.tenant_id == tenant_id))
        agent_count = agent_result.scalar() or 0

        # Count configured tools
        tool_result = await db.execute(
            select(func.count(TenantToolConfig.id)).where(
                TenantToolConfig.tenant_id == tenant_id
            )
        )
        tool_count = tool_result.scalar() or 0

        return {
            "tenant_id": tenant_id,
            "tenant_name": tenant.tenant_name,
            "user_count": user_count,
            "department_count": dept_count,
            "agent_count": agent_count,
            "configured_tools_count": tool_count,
            "created_at": tenant.created_at.isoformat() if tenant.created_at else None,
            "last_updated": tenant.updated_at.isoformat() if tenant.updated_at else None
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get tenant usage: {str(e)}"
        )


@router.get("/health/detailed", summary="Get detailed system health (MAINTAINER only)")
async def get_detailed_health(
    db: AsyncSession = Depends(get_db),
    maintainer: dict = Depends(RequireOnlyMaintainer())
) -> Dict[str, Any]:
    """Get detailed system health information (MAINTAINER only)"""
    try:
        from models.database.tenant import Tenant
        from models.database.user import User
        from models.database.agent import Agent, WorkflowAgent
        from models.database.tool import Tool, TenantToolConfig
        from models.database.provider import Provider

        # Database connectivity
        db_status = "healthy"
        try:
            await db.execute(select(func.count(Tenant.id)).limit(1))
        except Exception:
            db_status = "unhealthy"

        # Count resources
        tenant_count = (await db.execute(select(func.count(Tenant.id)))).scalar() or 0
        user_count = (await db.execute(select(func.count(User.id)))).scalar() or 0
        agent_count = (await db.execute(select(func.count(Agent.id)))).scalar() or 0
        tool_count = (await db.execute(select(func.count(Tool.id)))).scalar() or 0
        provider_count = (await db.execute(select(func.count(Provider.id)))).scalar() or 0

        # Workflow agents status
        workflow_count = (await db.execute(select(func.count(WorkflowAgent.id)))).scalar() or 0
        active_workflows = (await db.execute(
            select(func.count(WorkflowAgent.id)).where(WorkflowAgent.is_active == True)
        )).scalar() or 0

        return {
            "database": {
                "status": db_status,
                "connection": "ok" if db_status == "healthy" else "failed"
            },
            "resources": {
                "tenants": tenant_count,
                "users": user_count,
                "agents": agent_count,
                "tools": tool_count,
                "providers": provider_count
            },
            "workflows": {
                "total": workflow_count,
                "active": active_workflows,
                "inactive": workflow_count - active_workflows
            },
            "system_load": {
                "cpu_percent": 45.2,  # Mock data
                "memory_percent": 62.8,
                "disk_percent": 34.1
            },
            "overall_status": "healthy" if db_status == "healthy" and tenant_count > 0 else "warning"
        }

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get detailed health: {str(e)}"
        )
