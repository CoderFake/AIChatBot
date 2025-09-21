from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from config.database import get_db
from services.tenant.tenant_service import get_tenant_service
from api.v1.middleware.middleware import (
    RequireOnlyMaintainer,
    RequireOnlyAdmin,
    RequireAdminOrDeptAdmin,
    RequireAtLeastDeptAdmin,
    RequireAtLeastDeptManager
)
from models.schemas.request.tenant import CreateTenantRequest, UpdateTenantRequest
from models.schemas.responses.tenant import (
    TenantResponse,
    TenantListResponse,
    CreateTenantResponse,
    OperationResult,
    TenantPublicInfoResponse,
)
from models.database.tenant import Department

router = APIRouter()


@router.post("", response_model=CreateTenantResponse, summary="Create a new tenant with optional provider and tools setup")
async def create_tenant(
    payload: CreateTenantRequest,
    maintainer: dict = Depends(RequireOnlyMaintainer()),
    db: AsyncSession = Depends(get_db),
):
    service = await get_tenant_service(db)
    try:
        created_by = str(maintainer.get("user_id")) if isinstance(maintainer, dict) else "system"

        result = await service.create_tenant(
            tenant_name=payload.tenant_name,
            timezone=payload.timezone,
            locale=payload.locale or "en_US",
            sub_domain=payload.sub_domain,
            description=payload.description,
            allowed_providers=payload.allowed_providers,
            allowed_tools=payload.allowed_tools,
            created_by=created_by,
        )

        return CreateTenantResponse(**result)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("", response_model=TenantListResponse, summary="List tenants")
async def list_tenants(
    page: int = 1,
    limit: int = 20,
    is_active: bool | None = None,
    maintainer: dict = Depends(RequireOnlyMaintainer()),
    db: AsyncSession = Depends(get_db),
):
    service = await get_tenant_service(db)
    data = await service.list_tenants(page=page, limit=limit, is_active=is_active)

    return TenantListResponse(
        tenants=[
            TenantResponse(
                id=t["id"],
                tenant_name=t["tenant_name"],
                timezone=t["timezone"],
                locale=t["locale"],
                sub_domain=t.get("sub_domain"),
                is_active=t["is_active"],
                description=t.get("description"),
                created_at=t["created_at"],
                updated_at=t.get("updated_at") or t["created_at"],
            )
            for t in data["tenants"]
        ],
        total=data["total"],
        page=data["page"],
        limit=data["limit"],
        has_more=data["has_more"],
    )


@router.get("/{tenant_id}/public-info", response_model=TenantPublicInfoResponse, summary="Get public tenant info (no authentication required)")
async def get_tenant_public(
    tenant_id: str,
    db: AsyncSession = Depends(get_db),
) -> TenantPublicInfoResponse:
    service = await get_tenant_service(db)
    data = await service.get_tenant_public_info(tenant_id)
    if not data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found")

    return TenantPublicInfoResponse(
        id=data["id"],
        tenant_name=data["tenant_name"],
        locale=data["locale"],
        is_active=data["is_active"],
        description=data.get("description"),
        sub_domain=data.get("sub_domain"),
        logo_url=data.get("logo_url"),
        primary_color=data.get("primary_color") or "#6366f1",
    )


@router.get("/{tenant_id}", summary="Get tenant detail with allowed providers and tools")
async def get_tenant(
    tenant_id: str,
    db: AsyncSession = Depends(get_db),
):
    try:
        service = await get_tenant_service(db)
        data = await service.get_tenant_with_config(tenant_id)
        return data
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.put("/{tenant_id}", response_model=OperationResult, summary="Update tenant")
async def update_tenant(
    tenant_id: str,
    payload: UpdateTenantRequest,
    admin: dict = Depends(RequireOnlyMaintainer()),
    db: AsyncSession = Depends(get_db),
):
    service = await get_tenant_service(db)
    ok = await service.update_tenant(tenant_id, updates=payload.model_dump(exclude_none=True), updated_by=str(admin.get("user_id")) if isinstance(admin, dict) else "system")
    if not ok:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Update failed")
    return OperationResult(success=True)


@router.delete("/{tenant_id}", response_model=OperationResult, summary="Soft delete tenant")
async def delete_tenant(
    tenant_id: str,
    maintainer: dict = Depends(RequireOnlyMaintainer()),
    db: AsyncSession = Depends(get_db),
):
    service = await get_tenant_service(db)
    try:
        await service.update_tenant(
            tenant_id=tenant_id,
            updates={"is_active": False},
            updated_by=str(maintainer.get("user_id")) if isinstance(maintainer, dict) else "system"
        )
        return OperationResult(success=True)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Delete failed: {str(e)}")


@router.post("/configure-provider", summary="Configure provider for tenant")
async def configure_tenant_provider(
    tenant_id: str,
    provider_name: str,
    model_name: str,
    api_keys: list[str],
    provider_model_config: dict = None,
    admin: dict = Depends(RequireOnlyAdmin()),
    db: AsyncSession = Depends(get_db),
):
    """
    Configure provider with API keys for tenant
    """
    service = await get_tenant_service(db)
    try:
        result = await service.configure_tenant_provider(
            tenant_id=tenant_id,
            provider_name=provider_name,
            model_name=model_name,
            api_keys=api_keys,
            model_config=provider_model_config,
            configured_by=str(admin.get("user_id"))
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/setup-workflow-agent", summary="Setup workflow agent with provider")
async def setup_workflow_agent(
    tenant_id: str,
    provider_name: str,
    model_name: str,
    provider_model_config: dict = None,
    admin: dict = Depends(RequireOnlyAdmin()),
    db: AsyncSession = Depends(get_db),
):
    """
    Create or update WorkflowAgent with configured provider
    """
    service = await get_tenant_service(db)
    try:
        result = await service.create_workflow_agent_with_provider(
            tenant_id=tenant_id,
            provider_name=provider_name,
            model_name=model_name,
            model_config=provider_model_config,
            created_by=str(admin.get("user_id"))
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


# ==================== TOOL CONFIGURATION ENDPOINTS ====================

@router.post("/enable-tools", summary="Enable tools for tenant")
async def enable_tenant_tools(
    tenant_id: str,
    admin: dict = Depends(RequireOnlyAdmin()),
    db: AsyncSession = Depends(get_db),
):
    """
    Enable tools for tenant
    """
    service = await get_tenant_service(db)
    try:
        result = await service.enable_tenant_tools(
            tenant_id=tenant_id,
            enabled_by=str(admin.get("user_id"))
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/departments/{department_id}/enable-tools", summary="Enable tools for department")
async def enable_department_tools(
    department_id: str,
    admin: dict = Depends(RequireAdminOrDeptAdmin()),
    db: AsyncSession = Depends(get_db),
):
    """
    Enable tools for department (admin or dept admin only)
    """
    service = await get_tenant_service(db)
    try:
        result = await service.enable_department_tools(
            department_id=department_id,
            enabled_by=str(admin.get("user_id"))
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


# ==================== COMPLETE SETUP FLOW ENDPOINT ====================

@router.post("/complete-setup", summary="Complete tenant setup with provider, agent, and tools")
async def complete_tenant_setup(
    tenant_id: str,
    provider_name: str,
    model_name: str,
    api_keys: list[str],
    provider_model_config: dict = None,
    allowed_tools: list[str] = None,
    admin: dict = Depends(RequireOnlyAdmin()),
    db: AsyncSession = Depends(get_db),
):
    """
    Complete tenant setup in one API call:
    1. Configure provider with API keys
    2. Setup workflow agent
    3. Enable tools for tenant
    """
    service = await get_tenant_service(db)
    admin_user_id = str(admin.get("user_id"))

    try:
        provider_result = await service.configure_tenant_provider(
            tenant_id=tenant_id,
            provider_name=provider_name,
            model_name=model_name,
            api_keys=api_keys,
            model_config=provider_model_config,
            configured_by=admin_user_id
        )

        agent_result = await service.create_workflow_agent_with_provider(
            tenant_id=tenant_id,
            provider_name=provider_name,
            model_name=model_name,
            model_config=provider_model_config,
            created_by=admin_user_id
        )

        tools_result = None
        if allowed_tools:
            tools_result = await service.enable_tenant_tools(
                tenant_id=tenant_id,
                tool_ids=allowed_tools,
                enabled_by=admin_user_id
            )

        return {
            "success": True,
            "tenant_id": tenant_id,
            "setup_completed": True,
            "provider_config": provider_result,
            "workflow_agent": agent_result,
            "enabled_tools": tools_result,
            "orchestrator_ready": True
        }

    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


# ==================== INVITATION ENDPOINTS ====================

@router.post("/invite-department-admins", summary="Invite department administrators")
async def invite_department_admins(
    department_id: str,
    emails: List[str],
    db: AsyncSession = Depends(get_db),
    admin: dict = Depends(RequireOnlyAdmin()),
):
    """Admin invites department administrators to a department"""
    try:
        if not department_id or not emails:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Department ID and emails are required")

        dept_result = await db.execute(select(Department).where(Department.id == department_id))
        department = dept_result.scalar_one_or_none()
        if not department:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Department not found")

        service = await get_tenant_service(db)
        invite_service = await service.get_invite_service()

        invite_links = await invite_service.invite_department_admins(
            tenant_id=str(department.tenant_id),
            department_id=department_id,
            emails=emails,
            invited_by=admin.get("user_id")
        )

        return {
            "success": True,
            "message": f"Invited {len(emails)} department administrators",
            "invite_links": invite_links
        }

    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/invite-department-managers", summary="Invite department managers")
async def invite_department_managers(
    department_id: str,
    emails: List[str],
    db: AsyncSession = Depends(get_db),
    user_ctx: dict = Depends(RequireAtLeastDeptAdmin()),
):
    """Admin/Dept Admin invites department managers to a department"""
    try:
        if not department_id or not emails:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Department ID and emails are required")

        dept_result = await db.execute(select(Department).where(Department.id == department_id))
        department = dept_result.scalar_one_or_none()
        if not department:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Department not found")

        service = await get_tenant_service(db)
        invite_service = await service.get_invite_service()

        invite_links = await invite_service.invite_department_managers(
            tenant_id=str(department.tenant_id),
            department_id=department_id,
            emails=emails,
            invited_by=user_ctx.get("user_id")
        )

        return {
            "success": True,
            "message": f"Invited {len(emails)} department managers",
            "invite_links": invite_links
        }

    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/invite-users", summary="Invite users")
async def invite_users(
    department_id: str,
    emails: List[str],
    db: AsyncSession = Depends(get_db),
    user_ctx: dict = Depends(RequireAtLeastDeptManager()),
):
    """Admin/Dept Admin/Dept Manager invites users to a department"""
    try:
        if not department_id or not emails:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Department ID and emails are required")

        dept_result = await db.execute(select(Department).where(Department.id == department_id))
        department = dept_result.scalar_one_or_none()
        if not department:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Department not found")

        service = await get_tenant_service(db)
        invite_service = await service.get_invite_service()

        invite_links = await invite_service.invite_users(
            tenant_id=str(department.tenant_id),
            department_id=department_id,
            emails=emails,
            invited_by=user_ctx.get("user_id")
        )

        return {
            "success": True,
            "message": f"Invited {len(emails)} users",
            "invite_links": invite_links
        }

    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))






