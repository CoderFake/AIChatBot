"""User management endpoints"""
from typing import Any, Dict, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from config.database import get_db
from api.v1.middleware.middleware import RequireAtLeastAdmin
from models.database.user import User
from models.schemas.responses.user import UserResponse, UserListResponse

router = APIRouter()


@router.get("", response_model=UserListResponse, summary="List users with tenant filtering")
async def list_users(
    tenant_id: Optional[str] = Query(None, description="Filter by tenant ID"),
    department_id: Optional[str] = Query(None, description="Filter by department ID"),
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(20, ge=1, le=100, description="Items per page"),
    search: Optional[str] = Query(None, description="Search by username, email, or full name"),
    db: AsyncSession = Depends(get_db),
    user_ctx: dict = Depends(RequireAtLeastAdmin())
) -> UserListResponse:
    """List users with optional filtering by tenant, department, and search"""
    try:
        query = select(User).where(User.is_deleted == False)

        user_role = user_ctx.get("role")
        user_tenant_id = user_ctx.get("tenant_id")

        if user_role != "MAINTAINER":
            if not user_tenant_id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Tenant context required"
                )
            query = query.where(User.tenant_id == user_tenant_id)
        else:
            if tenant_id:
                query = query.where(User.tenant_id == tenant_id)

        if department_id:
            query = query.where(User.department_id == department_id)

        if is_active is not None:
            query = query.where(User.is_active == is_active)

        if search:
            search_term = f"%{search}%"
            query = query.where(
                (User.username.ilike(search_term)) |
                (User.email.ilike(search_term)) |
                ((User.first_name + " " + User.last_name).ilike(search_term))
            )

        count_query = query.with_only_columns(User.id)
        total_result = await db.execute(count_query)
        total = len(total_result.all())

        offset = (page - 1) * limit
        query = query.offset(offset).limit(limit)

        query = query.order_by(User.created_at.desc())

        result = await db.execute(query)
        users = result.scalars().all()

        user_responses = []
        for user in users:
            user_responses.append(UserResponse(
                id=str(user.id),
                username=user.username,
                email=user.email,
                full_name=user.get_full_name() if hasattr(user, 'get_full_name') else f"{user.first_name or ''} {user.last_name or ''}".strip(),
                role=user.role,
                tenant_id=str(user.tenant_id) if user.tenant_id else None,
                department_id=str(user.department_id) if user.department_id else None,
                is_active=user.is_active,
                is_verified=user.is_verified,
                last_login=user.last_login.isoformat() if user.last_login else None,
                created_at=user.created_at.isoformat() if user.created_at else None,
            ))

        return UserListResponse(
            users=user_responses,
            total=total,
            page=page,
            limit=limit,
            has_more=(page * limit) < total
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list users: {str(e)}"
        )


@router.get("/{user_id}", response_model=UserResponse, summary="Get user details")
async def get_user(
    user_id: str,
    db: AsyncSession = Depends(get_db),
    user_ctx: dict = Depends(RequireAtLeastAdmin())
) -> UserResponse:
    """Get detailed information about a specific user"""
    try:
        query = select(User).where(
            User.id == user_id,
            User.is_deleted == False
        )

        user_role = user_ctx.get("role")
        user_tenant_id = user_ctx.get("tenant_id")

        if user_role != "MAINTAINER":
            if not user_tenant_id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Tenant context required"
                )
            query = query.where(User.tenant_id == user_tenant_id)

        result = await db.execute(query)
        user = result.scalar_one_or_none()

        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )

        return UserResponse(
            id=str(user.id),
            username=user.username,
            email=user.email,
            full_name=user.get_full_name() if hasattr(user, 'get_full_name') else f"{user.first_name or ''} {user.last_name or ''}".strip(),
            role=user.role,
            tenant_id=str(user.tenant_id) if user.tenant_id else None,
            department_id=str(user.department_id) if user.department_id else None,
            is_active=user.is_active,
            is_verified=user.is_verified,
            last_login=user.last_login.isoformat() if user.last_login else None,
            created_at=user.created_at.isoformat() if user.created_at else None,
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get user: {str(e)}"
        )