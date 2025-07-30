"""
Configuration Manager
Database-driven configuration with tenant-based Redis caching
Uses CacheManager and RedisService for tenant-specific config management
"""

import asyncio
from typing import Dict, Any, List, Optional
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session
from sqlalchemy import select, and_

from config.settings import get_settings, Settings
from config.database import get_db, get_db_context
from services.cache.cache_manager import cache_manager
from services.cache.redis_service import redis_client
from utils.logging import get_logger
from utils.datetime_utils import CustomDateTime
from models.database.tenant import Tenant, Department
from models.database.provider import Provider, DepartmentProviderConfig
from models.database.agent import Agent, AgentToolConfig
from models.database.tool import Tool, DepartmentToolConfig
from models.database.user import User
from models.database.permission import UserPermission

logger = get_logger(__name__)


class ConfigManager:
    """
    Database-driven configuration manager with tenant-based Redis caching
    Delegates caching operations to CacheManager and RedisService
    """
    
    def __init__(self):
        self._current_settings: Optional[Settings] = None
        self._monitoring = False
        self._last_update = None
        self._initialized = False
        
        self._load_settings()
    
    def _load_settings(self) -> None:
        """Load settings from environment/config files"""
        try:
            self._current_settings = get_settings()
            logger.info("Configuration loaded successfully")
        except Exception as e:
            logger.error(f"Failed to load configuration: {e}")
            self._current_settings = Settings() 
    
    async def initialize(self):
        """Initialize config manager and cache services"""
        try:
            await cache_manager.initialize()
            await redis_client.initialize()
            self._initialized = True
            logger.info("Config manager initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize config manager: {e}")
            raise
    
    async def _ensure_initialized(self):
        """Ensure config manager is initialized"""
        if not self._initialized:
            await self.initialize()
    
    def _get_db_session(self) -> Optional[Session]:
        """Get database session"""
        try:
            db = next(get_db())
            return db
        except Exception as e:
            logger.error(f"Failed to get database session: {e}")
            return None
    
    async def load_tenant_providers_from_db(
        self, 
        tenant_id: str, 
        db_session: AsyncSession
    ) -> Dict[str, Any]:
        """Load tenant provider configurations from database"""
        try:
            result = await db_session.execute(
                select(Provider, DepartmentProviderConfig, Department)
                .join(DepartmentProviderConfig, Provider.id == DepartmentProviderConfig.provider_id)
                .join(Department, DepartmentProviderConfig.department_id == Department.id)
                .where(
                    and_(
                        Department.tenant_id == tenant_id,
                        Provider.is_enabled == True,
                        DepartmentProviderConfig.is_enabled == True
                    )
                )
            )
            
            tenant_providers = {}
            
            for provider, dept_config, department in result:
                provider_key = f"{provider.provider_code}_{department.department_code}"
                
                tenant_providers[provider_key] = {
                    "provider_code": provider.provider_code,
                    "provider_name": provider.provider_name,
                    "department_code": department.department_code,
                    "department_name": department.department_name,
                    "is_enabled": dept_config.is_enabled,
                    "api_key": dept_config.api_key,
                    "config_data": dept_config.config_data or {},
                    "base_config": provider.base_config or {},
                    "last_updated": CustomDateTime.now().isoformat()
                }
            
            logger.info(f"Loaded {len(tenant_providers)} providers for tenant {tenant_id}")
            return tenant_providers
            
        except Exception as e:
            logger.error(f"Failed to load tenant providers from DB: {e}")
            return {}
    
    async def load_tenant_agents_from_db(
        self, 
        tenant_id: str, 
        db_session: AsyncSession
    ) -> Dict[str, Any]:
        """Load tenant agent configurations from database"""
        try:
            result = await db_session.execute(
                select(Agent, Department)
                .join(Department, Agent.department_id == Department.id)
                .where(
                    and_(
                        Department.tenant_id == tenant_id,
                        Agent.is_enabled == True
                    )
                )
            )
            
            tenant_agents = {}
            
            for agent, department in result:
                tool_result = await db_session.execute(
                    select(AgentToolConfig, Tool)
                    .join(Tool, AgentToolConfig.tool_id == Tool.id)
                    .where(
                        and_(
                            AgentToolConfig.agent_id == agent.id,
                            AgentToolConfig.is_enabled == True,
                            Tool.is_enabled == True
                        )
                    )
                )
                
                agent_tools = []
                for tool_config, tool in tool_result:
                    agent_tools.append({
                        "tool_code": tool.tool_code,
                        "tool_name": tool.tool_name,
                        "category": tool.category,
                        "config_data": tool_config.config_data or {}
                    })
                
                tenant_agents[agent.agent_code] = {
                    "agent_code": agent.agent_code,
                    "agent_name": agent.agent_name,
                    "description": agent.description,
                    "department_code": department.department_code,
                    "department_name": department.department_name,
                    "is_enabled": agent.is_enabled,
                    "is_system": agent.is_system,
                    "tools": agent_tools,
                    "last_updated": CustomDateTime.now().isoformat()
                }
            
            logger.info(f"Loaded {len(tenant_agents)} agents for tenant {tenant_id}")
            return tenant_agents
            
        except Exception as e:
            logger.error(f"Failed to load tenant agents from DB: {e}")
            return {}
    
    async def load_tenant_tools_from_db(
        self, 
        tenant_id: str, 
        db_session: AsyncSession
    ) -> Dict[str, Any]:
        """Load tenant tool configurations from database"""
        try:
            result = await db_session.execute(
                select(Tool, DepartmentToolConfig, Department)
                .join(DepartmentToolConfig, Tool.id == DepartmentToolConfig.tool_id)
                .join(Department, DepartmentToolConfig.department_id == Department.id)
                .where(
                    and_(
                        Department.tenant_id == tenant_id,
                        Tool.is_enabled == True,
                        DepartmentToolConfig.is_enabled == True
                    )
                )
            )
            
            tenant_tools = {}
            
            for tool, dept_config, department in result:
                tool_key = f"{tool.tool_code}_{department.department_code}"
                
                tenant_tools[tool_key] = {
                    "tool_code": tool.tool_code,
                    "tool_name": tool.tool_name,
                    "description": tool.description,
                    "category": tool.category,
                    "department_code": department.department_code,
                    "department_name": department.department_name,
                    "is_enabled": dept_config.is_enabled,
                    "base_config": tool.base_config or {},
                    "config_data": dept_config.config_data or {},
                    "usage_limits": dept_config.usage_limits or {},
                    "last_updated": CustomDateTime.now().isoformat()
                }
            
            logger.info(f"Loaded {len(tenant_tools)} tools for tenant {tenant_id}")
            return tenant_tools
            
        except Exception as e:
            logger.error(f"Failed to load tenant tools from DB: {e}")
            return {}
    
    async def load_tenant_permissions_from_db(
        self, 
        tenant_id: str, 
        db_session: AsyncSession
    ) -> Dict[str, Any]:
        """Load tenant permission configurations from database"""
        try:
            user_result = await db_session.execute(
                select(User)
                .where(User.tenant_id == tenant_id)
            )
            
            tenant_permissions = {}
            
            for user in user_result.scalars():
                user_perms_result = await db_session.execute(
                    select(UserPermission)
                    .where(UserPermission.user_id == user.id)
                )
                
                user_permissions = [
                    {
                        "permission_id": str(perm.permission_id),
                        "granted_by": str(perm.granted_by) if perm.granted_by else None,
                        "expires_at": perm.expires_at.isoformat() if perm.expires_at else None,
                        "conditions": perm.conditions or {}
                    }
                    for perm in user_perms_result.scalars()
                ]
                
                tenant_permissions[str(user.id)] = {
                    "user_id": str(user.id),
                    "username": user.username,
                    "email": user.email,
                    "role": user.role,
                    "department_id": str(user.department_id),
                    "is_active": user.is_active,
                    "permissions": user_permissions,
                    "last_updated": CustomDateTime.now().isoformat()
                }
            
            logger.info(f"Loaded permissions for {len(tenant_permissions)} users in tenant {tenant_id}")
            return tenant_permissions
            
        except Exception as e:
            logger.error(f"Failed to load tenant permissions from DB: {e}")
            return {}
    
    async def get_tenant_providers(self, tenant_id: str) -> Dict[str, Any]:
        """Get tenant providers from cache or load from database"""
        await self._ensure_initialized()
        
        cache_key = await cache_manager.get_tenant_cache_key(tenant_id, "providers")
        
        # Try cache first using get_or_set pattern
        return await cache_manager.get_or_set(
            cache_key,
            self._load_providers_from_db,
            ttl=None,  # No expiration
            tenant_id=tenant_id
        )
    
    async def get_tenant_agents(self, tenant_id: str) -> Dict[str, Any]:
        """Get tenant agents from cache or load from database"""
        await self._ensure_initialized()
        
        cache_key = await cache_manager.get_tenant_cache_key(tenant_id, "agents")
        
        return await cache_manager.get_or_set(
            cache_key,
            self._load_agents_from_db,
            ttl=None,  # No expiration
            tenant_id=tenant_id
        )
    
    async def get_tenant_tools(self, tenant_id: str) -> Dict[str, Any]:
        """Get tenant tools from cache or load from database"""
        await self._ensure_initialized()
        
        cache_key = await cache_manager.get_tenant_cache_key(tenant_id, "tools")
        
        return await cache_manager.get_or_set(
            cache_key,
            self._load_tools_from_db,
            ttl=None,  # No expiration
            tenant_id=tenant_id
        )
    
    async def get_tenant_permissions(self, tenant_id: str) -> Dict[str, Any]:
        """Get tenant permissions from cache or load from database"""
        await self._ensure_initialized()
        
        cache_key = await cache_manager.get_tenant_cache_key(tenant_id, "permissions")
        
        return await cache_manager.get_or_set(
            cache_key,
            self._load_permissions_from_db,
            ttl=None,  # No expiration
            tenant_id=tenant_id
        )
    
    async def _load_providers_from_db(self, tenant_id: str) -> Dict[str, Any]:
        """Helper method for loading providers from database"""
        async with get_db_context() as db:
            return await self.load_tenant_providers_from_db(tenant_id, db)
    
    async def _load_agents_from_db(self, tenant_id: str) -> Dict[str, Any]:
        """Helper method for loading agents from database"""
        async with get_db_context() as db:
            return await self.load_tenant_agents_from_db(tenant_id, db)
    
    async def _load_tools_from_db(self, tenant_id: str) -> Dict[str, Any]:
        """Helper method for loading tools from database"""
        async with get_db_context() as db:
            return await self.load_tenant_tools_from_db(tenant_id, db)
    
    async def _load_permissions_from_db(self, tenant_id: str) -> Dict[str, Any]:
        """Helper method for loading permissions from database"""
        async with get_db_context() as db:
            return await self.load_tenant_permissions_from_db(tenant_id, db)
    
    async def invalidate_tenant_cache(self, tenant_id: str) -> int:
        """Invalidate all cache for specific tenant"""
        await self._ensure_initialized()
        
        try:
            deleted_count = await cache_manager.invalidate_tenant_cache(tenant_id)
            logger.info(f"Invalidated {deleted_count} cache keys for tenant {tenant_id}")
            return deleted_count
            
        except Exception as e:
            logger.error(f"Failed to invalidate tenant cache: {e}")
            return 0
    
    async def refresh_tenant_cache(
        self, 
        tenant_id: str,
        cache_types: Optional[List[str]] = None
    ):
        """
        Refresh tenant cache from database
        cache_types: ['providers', 'agents', 'tools', 'permissions'] or None for all
        """
        await self._ensure_initialized()
        
        if cache_types is None:
            cache_types = ['providers', 'agents', 'tools', 'permissions']
        
        for cache_type in cache_types:
            try:
                cache_key = await cache_manager.get_tenant_cache_key(tenant_id, cache_type)
                
                # Delete existing cache
                await cache_manager.delete(cache_key)
                
                # Reload from database
                if cache_type == 'providers':
                    await self.get_tenant_providers(tenant_id)
                elif cache_type == 'agents':
                    await self.get_tenant_agents(tenant_id)
                elif cache_type == 'tools':
                    await self.get_tenant_tools(tenant_id)
                elif cache_type == 'permissions':
                    await self.get_tenant_permissions(tenant_id)
                
                logger.info(f"Refreshed {cache_type} cache for tenant {tenant_id}")
                
            except Exception as e:
                logger.error(f"Failed to refresh {cache_type} cache for tenant {tenant_id}: {e}")
    
    async def initialize_all_tenant_caches(self):
        """Initialize cache for all tenants on startup"""
        try:
            async with get_db_context() as db:
                # Get all active tenants
                result = await db.execute(select(Tenant).where(Tenant.is_active == True))
                tenants = result.scalars().all()
                
                logger.info(f"Initializing cache for {len(tenants)} tenants")
                
                # Load cache for each tenant concurrently
                tasks = []
                for tenant in tenants:
                    task = self._initialize_tenant_cache(str(tenant.id))
                    tasks.append(task)
                
                await asyncio.gather(*tasks, return_exceptions=True)
                
                logger.info(f"Completed cache initialization for all tenants")
                
        except Exception as e:
            logger.error(f"Failed to initialize tenant caches: {e}")
            raise
    
    async def _initialize_tenant_cache(self, tenant_id: str):
        """Initialize cache for single tenant"""
        try:
            # Load all cache types for this tenant
            await asyncio.gather(
                self.get_tenant_providers(tenant_id),
                self.get_tenant_agents(tenant_id),
                self.get_tenant_tools(tenant_id),
                self.get_tenant_permissions(tenant_id),
                return_exceptions=True
            )
            logger.debug(f"Initialized cache for tenant {tenant_id}")
            
        except Exception as e:
            logger.error(f"Failed to initialize cache for tenant {tenant_id}: {e}")
    
    async def get_tenant_config_summary(self, tenant_id: str) -> Dict[str, Any]:
        """Get summary of tenant configuration"""
        await self._ensure_initialized()
        
        try:
            providers = await self.get_tenant_providers(tenant_id)
            agents = await self.get_tenant_agents(tenant_id)
            tools = await self.get_tenant_tools(tenant_id)
            permissions = await self.get_tenant_permissions(tenant_id)
            
            return {
                "tenant_id": tenant_id,
                "providers": {
                    "count": len(providers),
                    "enabled": len([p for p in providers.values() if p.get("is_enabled")])
                },
                "agents": {
                    "count": len(agents),
                    "enabled": len([a for a in agents.values() if a.get("is_enabled")])
                },
                "tools": {
                    "count": len(tools),
                    "enabled": len([t for t in tools.values() if t.get("is_enabled")])
                },
                "users": {
                    "count": len(permissions),
                    "active": len([u for u in permissions.values() if u.get("is_active")])
                },
                "last_updated": CustomDateTime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Failed to get tenant config summary: {e}")
            return {}
    
    def get_current_config(self) -> Dict[str, Any]:
        """Get current system configuration (non-tenant specific)"""
        config = {}
        
        if hasattr(self._current_settings, 'workflow') and self._current_settings.workflow:
            config["workflow"] = {
                "max_iterations": self._current_settings.workflow.max_iterations,
                "timeout_seconds": self._current_settings.workflow.timeout_seconds,
                "enable_reflection": self._current_settings.workflow.enable_reflection,
                "enable_semantic_routing": self._current_settings.workflow.enable_semantic_routing,
                "checkpointer_type": self._current_settings.workflow.checkpointer_type
            }
        
        if hasattr(self._current_settings, 'orchestrator') and self._current_settings.orchestrator:
            config["orchestrator"] = {
                "enabled": self._current_settings.orchestrator.enabled,
                "strategy": self._current_settings.orchestrator.strategy,
                "max_agents_per_query": self._current_settings.orchestrator.max_agents_per_query,
                "confidence_threshold": self._current_settings.orchestrator.confidence_threshold
            }
        
        config["system"] = {
            "app_name": self._current_settings.APP_NAME,
            "app_version": self._current_settings.APP_VERSION,
            "environment": self._current_settings.ENV,
            "debug": self._current_settings.DEBUG
        }
        
        return config
    
    async def get_cache_stats(self) -> Dict[str, Any]:
        """Get comprehensive cache statistics"""
        await self._ensure_initialized()
        
        cache_stats = await cache_manager.get_cache_stats()
        redis_health = await redis_client.health_check()
        
        return {
            "cache_manager": cache_stats,
            "redis_service": redis_health,
            "initialized": self._initialized,
            "monitoring": self._monitoring
        }
    
    async def start_monitoring(self):
        """Start configuration monitoring"""
        self._monitoring = True
        logger.info("Configuration monitoring started")
        
        while self._monitoring:
            try:
                await asyncio.sleep(300)
                
                self._last_update = datetime.now()
                logger.debug("Configuration monitoring heartbeat")
                
            except Exception as e:
                logger.error(f"Configuration monitoring error: {e}")
                await asyncio.sleep(60) 
    
    async def stop_monitoring(self):
        """Stop configuration monitoring"""
        self._monitoring = False
        await redis_client.close()
        logger.info("Configuration monitoring stopped")


config_manager = ConfigManager()