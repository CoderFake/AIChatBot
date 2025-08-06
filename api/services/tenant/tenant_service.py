# api/services/tenant/tenant_service.py
"""
Tenant Service
Handle tenant CRUD operations
No validation at service layer
"""
from typing import List, Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete
from datetime import datetime
import uuid

from models.database.tenant import Tenant, Department
from models.database.user import User
from services.auth.permission_service import PermissionService
from utils.logging import get_logger

logger = get_logger(__name__)


class TenantService:
    """
    Service for tenant management operations
    Used by maintainer-level operations
    """
    
    def __init__(self, db: AsyncSession):
        self.db = db
        self.permission_service = PermissionService(db)
    
    async def create_tenant(
        self,
        tenant_name: str,
        created_by: str,
        config: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Create new tenant with default setup
        """
        try:
            result = await self.permission_service.create_tenant_with_defaults(
                tenant_name=tenant_name,
                created_by=created_by,
                config=config
            )
            
            logger.info(f"Created tenant: {tenant_name}")
            return result
            
        except Exception as e:
            logger.error(f"Failed to create tenant: {e}")
            raise
    
    async def get_tenant_by_id(self, tenant_id: str) -> Optional[Dict[str, Any]]:
        """
        Get tenant by ID
        """
        try:
            result = await self.db.execute(
                select(Tenant).where(Tenant.id == tenant_id)
            )
            tenant = result.scalar_one_or_none()
            
            if not tenant:
                return None
            
            return {
                "tenant_id": str(tenant.id),
                "tenant_name": tenant.tenant_name,
                "is_active": tenant.is_active,
                "config": tenant.config or {},
                "created_at": tenant.created_at.isoformat() if tenant.created_at else None,
                "created_by": tenant.created_by,
                "updated_at": tenant.updated_at.isoformat() if tenant.updated_at else None,
                "updated_by": tenant.updated_by
            }
            
        except Exception as e:
            logger.error(f"Failed to get tenant: {e}")
            return None
    
    async def get_all_tenants(self, include_inactive: bool = False) -> List[Dict[str, Any]]:
        """
        Get all tenants
        """
        try:
            return await self.permission_service.get_tenant_list(include_inactive)
        except Exception as e:
            logger.error(f"Failed to get tenant list: {e}")
            return []
    
    async def update_tenant(
        self,
        tenant_id: str,
        tenant_name: Optional[str] = None,
        config: Optional[Dict[str, Any]] = None,
        updated_by: Optional[str] = None
    ) -> bool:
        """
        Update tenant information
        """
        try:
            update_data = {
                "updated_at": datetime.utcnow(),
                "updated_by": updated_by
            }
            
            if tenant_name:
                update_data["tenant_name"] = tenant_name
            if config is not None:
                update_data["config"] = config
            
            result = await self.db.execute(
                update(Tenant)
                .where(Tenant.id == tenant_id)
                .values(**update_data)
            )
            
            await self.db.commit()
            success = result.rowcount > 0
            
            if success:
                logger.info(f"Updated tenant {tenant_id}")
            else:
                logger.warning(f"Tenant {tenant_id} not found for update")
            
            return success
            
        except Exception as e:
            await self.db.rollback()
            logger.error(f"Failed to update tenant: {e}")
            raise
    
    async def soft_delete_tenant(self, tenant_id: str, deleted_by: str) -> bool:
        """
        Soft delete tenant
        """
        try:
            return await self.permission_service.soft_delete_tenant(tenant_id, deleted_by)
        except Exception as e:
            logger.error(f"Failed to soft delete tenant: {e}")
            raise
    
    async def hard_delete_tenant(self, tenant_id: str) -> bool:
        """
        Hard delete tenant
        """
        try:
            return await self.permission_service.hard_delete_tenant(tenant_id)
        except Exception as e:
            logger.error(f"Failed to hard delete tenant: {e}")
            raise
    
    async def restore_tenant(self, tenant_id: str, restored_by: str) -> bool:
        """
        Restore soft-deleted tenant
        """
        try:
            result = await self.db.execute(
                update(Tenant)
                .where(Tenant.id == tenant_id)
                .values(
                    is_active=True,
                    updated_at=datetime.utcnow(),
                    updated_by=restored_by
                )
            )
            
            await self.db.commit()
            success = result.rowcount > 0
            
            if success:
                logger.info(f"Restored tenant {tenant_id}")
            else:
                logger.warning(f"Tenant {tenant_id} not found for restore")
            
            return success
            
        except Exception as e:
            await self.db.rollback()
            logger.error(f"Failed to restore tenant: {e}")
            raise
    
    async def get_tenant_stats(self, tenant_id: str) -> Dict[str, Any]:
        """
        Get tenant statistics
        """
        try:
            # Count departments
            dept_result = await self.db.execute(
                select(Department).where(
                    Department.tenant_id == tenant_id,
                    Department.is_active == True
                )
            )
            dept_count = len(dept_result.scalars().all())
            
            # Count users
            user_result = await self.db.execute(
                select(User).where(
                    User.tenant_id == tenant_id,
                    User.is_active == True
                )
            )
            user_count = len(user_result.scalars().all())
            
            return {
                "tenant_id": tenant_id,
                "department_count": dept_count,
                "user_count": user_count
            }
            
        except Exception as e:
            logger.error(f"Failed to get tenant stats: {e}")
            return {
                "tenant_id": tenant_id,
                "department_count": 0,
                "user_count": 0
            }