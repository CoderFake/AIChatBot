from typing import Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.ext.asyncio import AsyncSession

from config.database import get_db
from services.tenant.tenant_service import get_tenant_service
from api.v1.middleware.middleware import (
    RequireOnlyMaintainer,
    RequireOnlyAdmin,
    RequireAdminOrDeptAdmin,
)
from models.schemas.request.tenant import CreateTenantRequest, UpdateTenantRequest
from models.schemas.responses.tenant import TenantResponse, TenantListResponse, CreateTenantResponse, OperationResult

router = APIRouter(prefix="/tenants", tags=["Tenants"])


@router.post("", response_model=CreateTenantResponse, summary="Create a new tenant")
async def create_tenant_endpoint(
    payload: CreateTenantRequest,
    maintainer = RequireOnlyMaintainer(),
    db: AsyncSession = Depends(get_db),
):
    service = await get_tenant_service(db)
    try:
        result = await service.create_tenant(
            tenant_name=payload.tenant_name,
            timezone=payload.timezone,
            locale=payload.locale or "en_US",
            sub_domain=payload.sub_domain,
            description=payload.description,
            created_by=str(maintainer.get("user_id")) if isinstance(maintainer, dict) else "system",
        )

        if payload.workflow_provider or payload.workflow_model:
            await service.create_default_workflow_agent(
                tenant_id=result["tenant_id"],
                provider_name=payload.workflow_provider,
                model_name=payload.workflow_model,
                created_by=str(maintainer.get("user_id")) if isinstance(maintainer, dict) else "system",
            )
        return CreateTenantResponse(**result)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("", response_model=TenantListResponse, summary="List tenants")
async def list_tenants_endpoint(
    page: int = 1,
    limit: int = 20,
    is_active: bool | None = None,
    maintainer = RequireOnlyMaintainer(),
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


@router.get("/{tenant_id}", response_model=TenantResponse, summary="Get tenant detail")
async def get_tenant_endpoint(
    tenant_id: str,
    admin = RequireAdminOrDeptAdmin(),
    db: AsyncSession = Depends(get_db),
):
    service = await get_tenant_service(db)
    data = await service.get_tenant_by_id(tenant_id)
    if not data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found")
    return TenantResponse(
        id=data["id"],
        tenant_name=data["tenant_name"],
        timezone=data["timezone"],
        locale=data["locale"],
        sub_domain=data.get("sub_domain"),
        is_active=data["is_active"],
        description=(data.get("settings") or {}).get("description") or None if isinstance(data.get("settings"), dict) else None,
        created_at=data["created_at"],
        updated_at=data["updated_at"],
    )


@router.put("/{tenant_id}", response_model=OperationResult, summary="Update tenant")
async def update_tenant_endpoint(
    tenant_id: str,
    payload: UpdateTenantRequest,
    admin = RequireOnlyAdmin(),
    db: AsyncSession = Depends(get_db),
):
    service = await get_tenant_service(db)
    ok = await service.update_tenant(tenant_id, updates=payload.model_dump(exclude_none=True), updated_by=str(admin.get("user_id")) if isinstance(admin, dict) else "system")
    if not ok:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Update failed")
    return OperationResult(success=True)


@router.delete("/{tenant_id}", response_model=OperationResult, summary="Soft delete tenant")
async def delete_tenant_endpoint(
    tenant_id: str,
    maintainer = RequireOnlyMaintainer(),
    db: AsyncSession = Depends(get_db),
):
    service = await get_tenant_service(db)
    ok = await service.update_tenant(tenant_id, updates={"is_active": False}, updated_by=str(maintainer.get("user_id")) if isinstance(maintainer, dict) else "system")
    if not ok:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Delete failed")
    return OperationResult(success=True)


