from typing import List, Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from sqlalchemy.orm import selectinload

from models.database.tenant import Tenant
from models.database.provider import WorkflowAgent
from services.auth.permission_service import PermissionService
from services.cache.redis_service import redis_service
from utils.datetime_utils import CustomDateTime, TenantDateTimeManager
from common.types import DefaultProviderConfig
from utils.logging import get_logger
from core.exceptions import ServiceError

logger = get_logger(__name__)


class TenantService:
    """
    Service for tenant management operations with timezone support
    """
    
    def __init__(self, db: AsyncSession):
        self.db = db
        self.permission_service = PermissionService(db)
    
    async def create_tenant(
        self,
        tenant_name: str,
        timezone: str = "UTC",
        locale: str = "en_US",
        created_by: str = "system",
        config: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Create new tenant with WorkflowAgent and timezone configuration
        """
        try:
            tenant = Tenant(
                tenant_name=tenant_name,
                timezone=timezone,
                locale=locale,
                settings=config or {},
                created_by=created_by
            )
            
            self.db.add(tenant)
            await self.db.flush()  
            workflow_agent = await self._create_workflow_agent(
                tenant_id=tenant.id
            )
            
            default_groups = await self.permission_service.create_default_groups_for_tenant(
                tenant_id=tenant.id,
                created_by=created_by
            )
            
            await self.db.commit()
            
            await self._load_tenant_to_cache(tenant)
            
            await self._load_tenant_config_to_redis(tenant.id)
            
            result = {
                "tenant_id": str(tenant.id),
                "tenant_name": tenant.tenant_name,
                "timezone": tenant.timezone,
                "locale": tenant.locale,
                "workflow_agent_id": str(workflow_agent.id),
                "default_groups": default_groups,
                "created_at": tenant.created_at.isoformat()
            }
            
            logger.info(f"Created tenant: {tenant_name} with timezone {timezone}")
            return result
            
        except Exception as e:
            await self.db.rollback()
            logger.error(f"Failed to create tenant: {e}")
            raise ServiceError(f"Failed to create tenant: {str(e)}")
    
    async def _create_workflow_agent(
        self,
        tenant_id: str
    ) -> WorkflowAgent:
        """
        Create WorkflowAgent for tenant with default configuration
        API key is set to None - tenant will configure later
        """
        workflow_agent = WorkflowAgent(
            tenant_id=tenant_id,
            provider_name=DefaultProviderConfig.PROVIDER_NAME.value,  
            model_name=DefaultProviderConfig.DEFAULT_MODEL.value,
            model_config={
                "temperature": DefaultProviderConfig.DEFAULT_TEMPERATURE,
                "max_tokens": DefaultProviderConfig.DEFAULT_MAX_TOKENS,
                "top_p": DefaultProviderConfig.DEFAULT_TOP_P
            },
            max_iterations=10,
            timeout_seconds=300,
            confidence_threshold=0.7
        )
        
        self.db.add(workflow_agent)
        await self.db.flush()
        
        logger.info(f"Created default WorkflowAgent for tenant {tenant_id} (key: none)")
        return workflow_agent
    
    async def get_tenant_by_id(self, tenant_id: str) -> Optional[Dict[str, Any]]:
        """
        Get tenant by ID with WorkflowAgent information
        """
        try:
            result = await self.db.execute(
                select(Tenant)
                .options(selectinload(Tenant.workflow_agent))
                .where(Tenant.id == tenant_id)
            )
            tenant = result.scalar_one_or_none()
            
            if not tenant:
                return None
            
            return {
                "id": str(tenant.id),
                "tenant_name": tenant.tenant_name,
                "timezone": tenant.timezone,
                "locale": tenant.locale,
                "is_active": tenant.is_active,
                "settings": tenant.settings,
                "workflow_agent": {
                    "id": str(tenant.workflow_agent.id),
                    "provider_name": tenant.workflow_agent.provider_name,
                    "model_name": tenant.workflow_agent.model_name,
                    "model_config": tenant.workflow_agent.model_config,
                    "max_iterations": tenant.workflow_agent.max_iterations,
                    "timeout_seconds": tenant.workflow_agent.timeout_seconds,
                    "confidence_threshold": tenant.workflow_agent.confidence_threshold,
                    "is_active": tenant.workflow_agent.is_active
                } if tenant.workflow_agent else None,
                "created_at": tenant.created_at.isoformat(),
                "updated_at": tenant.updated_at.isoformat()
            }
            
        except Exception as e:
            logger.error(f"Failed to get tenant {tenant_id}: {e}")
            return None
    
    async def update_tenant(
        self,
        tenant_id: str,
        updates: Dict[str, Any],
        updated_by: str
    ) -> bool:
        """
        Update tenant information including timezone
        """
        try:
            if "timezone" in updates:
                logger.info(f"Updating timezone for tenant {tenant_id} to {updates['timezone']}")
            
            updates["updated_by"] = updated_by
            
            await self.db.execute(
                update(Tenant)
                .where(Tenant.id == tenant_id)
                .values(**updates)
            )
            
            await self.db.commit()
            
            if "timezone" in updates:
                result = await self.db.execute(
                    select(Tenant).where(Tenant.id == tenant_id)
                )
                tenant = result.scalar_one_or_none()
                if tenant:
                    await self._load_tenant_to_cache(tenant)
            
            logger.info(f"Updated tenant {tenant_id}")
            return True
            
        except Exception as e:
            await self.db.rollback()
            logger.error(f"Failed to update tenant {tenant_id}: {e}")
            raise ServiceError(f"Failed to update tenant: {str(e)}")
    
    async def update_workflow_agent(
        self,
        tenant_id: str,
        workflow_config: Dict[str, Any],
        updated_by: str
    ) -> bool:
        """
        Update WorkflowAgent configuration for tenant
        """
        try:
            await self.db.execute(
                update(WorkflowAgent)
                .where(WorkflowAgent.tenant_id == tenant_id)
                .values(**workflow_config, updated_by=updated_by)
            )
            
            await self.db.commit()
            
            await redis_service.delete_tenant_cache(tenant_id)
            
            logger.info(f"Updated WorkflowAgent for tenant {tenant_id}")
            return True
            
        except Exception as e:
            await self.db.rollback()
            logger.error(f"Failed to update WorkflowAgent for tenant {tenant_id}: {e}")
            raise ServiceError(f"Failed to update workflow configuration: {str(e)}")
    
    async def _load_tenant_to_cache(self, tenant: Tenant):
        """
        Load basic tenant info to Redis cache and set timezone context
        ConfigManager handles detailed config caching separately
        """
        try:
            tenant_cache_data = {
                "tenant_id": str(tenant.id),
                "tenant_name": tenant.tenant_name,
                "timezone": tenant.timezone,
                "locale": tenant.locale,
                "is_active": tenant.is_active,
                "settings": tenant.settings or {},
                "cached_at": CustomDateTime.utc_now().isoformat()
            }
            
            # Load basic tenant data to cache
            await redis_service.cache_tenant_data(
                tenant_id=str(tenant.id),
                data=tenant_cache_data
            )
            
            # Set timezone context for datetime operations
            TenantDateTimeManager.set_tenant_context(tenant.timezone)
            
            logger.info(f"Loaded basic tenant {tenant.tenant_name} to cache with timezone {tenant.timezone}")
            
        except Exception as e:
            logger.error(f"Failed to load tenant to cache: {e}")
    
    async def _load_tenant_config_to_redis(self, tenant_id: str):
        """
        Load tenant configuration to ConfigManager Redis cache
        Includes providers, agents, tools, and workflow config
        """
        try:
            from config.config_manager import config_manager
            
            await config_manager.refresh_tenant_cache(tenant_id)
            
            logger.info(f"Loaded tenant {tenant_id} configuration to ConfigManager Redis cache")
            
        except Exception as e:
            logger.error(f"Failed to load tenant config to Redis: {e}")
    
    
    async def get_workflow_config(self, tenant_id: str) -> Optional[Dict[str, Any]]:
        """
        Get WorkflowAgent configuration for tenant
        """
        try:
            result = await self.db.execute(
                select(WorkflowAgent)
                .where(WorkflowAgent.tenant_id == tenant_id)
            )
            workflow_agent = result.scalar_one_or_none()
            
            if not workflow_agent:
                return None
            
            return workflow_agent.get_workflow_config()
            
        except Exception as e:
            logger.error(f"Failed to get workflow config for tenant {tenant_id}: {e}")
            return None
    
    async def list_tenants(
        self,
        page: int = 1,
        limit: int = 20,
        is_active: Optional[bool] = None
    ) -> Dict[str, Any]:
        """
        List tenants with pagination
        """
        try:
            query = select(Tenant).options(selectinload(Tenant.workflow_agent))
            
            if is_active is not None:
                query = query.where(Tenant.is_active == is_active)
            
            # Get total count
            count_result = await self.db.execute(
                select(select(Tenant).count()).select_from(
                    query.subquery()
                )
            )
            total = count_result.scalar()
            
            # Get paginated results
            query = query.offset((page - 1) * limit).limit(limit)
            result = await self.db.execute(query)
            tenants = result.scalars().all()
            
            tenant_list = []
            for tenant in tenants:
                tenant_data = {
                    "id": str(tenant.id),
                    "tenant_name": tenant.tenant_name,
                    "timezone": tenant.timezone,
                    "locale": tenant.locale,
                    "is_active": tenant.is_active,
                    "created_at": tenant.created_at.isoformat(),
                    "workflow_agent_active": tenant.workflow_agent.is_active if tenant.workflow_agent else False
                }
                tenant_list.append(tenant_data)
            
            return {
                "tenants": tenant_list,
                "total": total,
                "page": page,
                "limit": limit,
                "has_more": total > (page * limit)
            }
            
        except Exception as e:
            logger.error(f"Failed to list tenants: {e}")
            raise ServiceError(f"Failed to list tenants: {str(e)}")


async def get_tenant_service(db: AsyncSession) -> TenantService:
    """Get TenantService instance"""
    return TenantService(db)