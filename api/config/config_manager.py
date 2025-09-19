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
from services.tools.tool_service import ToolService
from services.llm.provider_service import ProviderService
from utils.logging import get_logger
from utils.datetime_utils import DateTimeManager
from models.database.tenant import Tenant, Department
from models.database.provider import Provider, TenantProviderConfig
from models.database.agent import Agent, WorkflowAgent
from models.database.tool import Tool, TenantToolConfig

logger = get_logger(__name__)


class ConfigManager:
    """
    Database-driven configuration manager with tenant-based Redis caching
    Supports multiple API keys with rotation for providers
    """
    
    def __init__(self):
        self._current_settings: Optional[Settings] = None
        self._monitoring = False
        self._last_update = None
        self._initialized = False
        
        self._load_settings()
    
    async def _get_tenant_timezone(self, tenant_id: str, db_session: AsyncSession) -> str:
        """Resolve tenant timezone; fallback to system timezone if unavailable."""
        try:
            result = await db_session.execute(select(Tenant).where(Tenant.id == tenant_id))
            tenant = result.scalar_one_or_none()
            if tenant and hasattr(tenant, "timezone") and tenant.timezone:
                return str(tenant.timezone)
        except Exception:
            pass
        return self.settings.TIMEZONE
    
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
            await redis_client.initialize()

            async with get_db_context() as db:
                tool_service = ToolService(db)
                await tool_service.initialize()

                provider_service = ProviderService(db)
                await provider_service.initialize()

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
        """
        Load tenant provider configurations from database
        Only cache providers/models that are actively used by department agents
        API keys are stored encrypted in DB and decrypted for cache usage
        """
        try:
            from models.database.agent import Agent
            
            result = await db_session.execute(
                select(Agent, Department, Provider, TenantProviderConfig)
                .join(Department, Agent.department_id == Department.id)
                .join(Provider, Agent.provider_id == Provider.id)
                .join(TenantProviderConfig, 
                      and_(
                          TenantProviderConfig.provider_id == Provider.id,
                          TenantProviderConfig.tenant_id == Department.tenant_id
                      ))
                .where(
                    and_(
                        Department.tenant_id == tenant_id,
                        Agent.is_enabled == True,
                        Department.is_active == True,
                        Provider.is_enabled == True,
                        TenantProviderConfig.is_enabled == True
                    )
                )
            )
            
            tenant_providers = {}
            
            for agent, department, provider, t_config in result:
                provider_key = f"{provider.id}_{department.id}"
                
                encrypted_keys = t_config.api_keys if t_config.api_keys else []
                
                if not encrypted_keys:
                    logger.warning(f"No API keys available for provider {provider.provider_name} in dept {department.department_name}")
                    continue
                
                cache_data = {
                    "provider_id": str(provider.id),
                    "provider_name": provider.provider_name,
                    "tenant_id": tenant_id,
                    "department_id": str(department.id),
                    "department_name": department.department_name,
                    "agent_id": str(agent.id),
                    "agent_name": agent.agent_name,
                    "model_id": str(agent.model_id) if agent.model_id else None,
                    "is_enabled": t_config.is_enabled,
                    "encrypted_api_keys": encrypted_keys,
                    "rotation_strategy": t_config.rotation_strategy,
                    "current_key_index": t_config.current_key_index,
                    "key_count": len(encrypted_keys),
                    "base_config": provider.base_config or {},
                    "config_data": t_config.config_data or {},
                    "last_updated": DateTimeManager._now().isoformat()
                }
                
                tenant_providers[provider_key] = cache_data
            
            logger.info(f"Loaded {len(tenant_providers)} active provider configs for tenant {tenant_id}")
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
            tz = await self._get_tenant_timezone(tenant_id, db_session)
            result = await db_session.execute( 
                select(Agent, Department)
                .join(Department, Agent.department_id == Department.id)
                .where(
                    and_(
                        Department.tenant_id == tenant_id,
                        Agent.is_enabled == True,
                        Department.is_active == True
                    )
                )
            )
            
            tenant_agents = {}
            
            for agent, department in result:
                agent_key = f"{agent.id}_{department.id}"
                
                tenant_agents[agent_key] = {
                    "agent_id": str(agent.id),
                    "agent_name": agent.agent_name,
                    "department_id": str(department.id),
                    "department_name": department.department_name,
                    "description": agent.description,
                    "capabilities": agent.capabilities or {},
                    "system_prompt": agent.system_prompt,
                    "model_config": agent.model_config or {},
                    "last_updated": DateTimeManager._now().isoformat()
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
        """Load tenant tool configurations from database (tenant-level)"""
        try:
            tz = await self._get_tenant_timezone(tenant_id, db_session)
            result = await db_session.execute(
                select(Tool, TenantToolConfig)
                .join(TenantToolConfig, Tool.id == TenantToolConfig.tool_id)
                .where(
                    and_(
                        TenantToolConfig.tenant_id == tenant_id,
                        Tool.is_enabled == True,
                        TenantToolConfig.is_enabled == True
                    )
                )
            )
            
            tenant_tools = {}
            
            for tool, t_config in result:
                tool_key = f"{tool.id}_{tenant_id}"
                
                tenant_tools[tool_key] = {
                    "tool_id": str(tool.id),
                    "tool_name": tool.tool_name,
                    "category": tool.category,
                    "tenant_id": tenant_id,
                    "config_id": str(t_config.id),
                    "is_enabled": t_config.is_enabled,
                    "base_config": tool.base_config or {},
                    "config_data": t_config.config_data or {},
                    "last_updated": DateTimeManager._now().isoformat()
                }
            
            logger.info(f"Loaded {len(tenant_tools)} tools for tenant {tenant_id}")
            return tenant_tools
            
        except Exception as e:
            logger.error(f"Failed to load tenant tools from DB: {e}")
            return {}
    
    async def load_tenant_workflow_from_db(
        self, 
        tenant_id: str, 
        db_session: AsyncSession
    ) -> Dict[str, Any]:
        """Load tenant workflow configuration from database"""
        try:
            tz = await self._get_tenant_timezone(tenant_id, db_session)
            result = await db_session.execute(
                select(WorkflowAgent)
                .where(WorkflowAgent.tenant_id == tenant_id)
            )
            
            workflow_agent = result.scalar_one_or_none()
            
            if not workflow_agent:
                logger.warning(f"No WorkflowAgent found for tenant {tenant_id}")
                return {}
            
            workflow_config = {
                "workflow_agent_id": str(workflow_agent.id),
                "tenant_id": tenant_id,
                "provider_name": workflow_agent.provider_name or "none",
                "model_name": workflow_agent.model_name or "none", 
                "api_key": workflow_agent.api_key,
                "is_active": workflow_agent.is_active,
                "model_config": workflow_agent.model_config or {},
                "max_iterations": workflow_agent.max_iterations,
                "timeout_seconds": workflow_agent.timeout_seconds,
                "confidence_threshold": workflow_agent.confidence_threshold,
                "last_updated": DateTimeManager._now().isoformat()
            }
            
            logger.info(f"Loaded workflow config for tenant {tenant_id}")
            return {"workflow": workflow_config}
            
        except Exception as e:
            logger.error(f"Failed to load tenant workflow from DB: {e}")
            return {}
    
    async def update_provider_key_rotation(
        self,
        tenant_id: str,
        provider_id: str,
        department_id: str,
        new_key_index: int,
        db_session: Optional[AsyncSession] = None
    ) -> bool:
        """
        Update provider API key rotation index in both database and cache
        """
        try:
            if db_session:
                result = await db_session.execute(
                    select(TenantProviderConfig)
                    .where(
                        and_(
                            TenantProviderConfig.tenant_id == tenant_id,
                            TenantProviderConfig.provider_id == provider_id
                        )
                    )
                )
                t_config = result.scalar_one_or_none()
                if t_config:
                    t_config.current_key_index = new_key_index
                    await db_session.commit()
                    await self._update_provider_cache(tenant_id, provider_id, department_id, new_key_index)
                    logger.info(f"Updated key rotation for provider {provider_id} (tenant-level), reflected for dept {department_id}")
                    return True
             
            return False
             
        except Exception as e:
            logger.error(f"Failed to update provider key rotation: {e}")
            return False
    
    async def _update_provider_cache(
        self,
        tenant_id: str,
        provider_id: str,
        department_id: str,
        new_key_index: int
    ):
        """
        Update specific provider configuration in cache
        """
        try:
            await self._ensure_initialized()
            
            provider_key = f"{provider_id}_{department_id}"
            cache_key = f"tenant:{tenant_id}:providers"
            
            cached_providers = await cache_manager.get_dict(cache_key) or {}
            
            if provider_key in cached_providers:
                cached_providers[provider_key]["current_key_index"] = new_key_index
                cached_providers[provider_key]["last_updated"] = DateTimeManager.maintainer_now().isoformat()
                
                await cache_manager.set_dict(
                    cache_key,
                    cached_providers
                )
                
                logger.debug(f"Updated provider cache for {provider_key}")
            
        except Exception as e:
            logger.error(f"Failed to update provider cache: {e}")
    
    async def get_tenant_providers(self, tenant_id: str) -> Dict[str, Any]:
        """
        Get tenant providers with caching
        Returns providers with current API key rotation state
        """
        try:
            await self._ensure_initialized()
            
            cache_key = f"tenant:{tenant_id}:providers"
            
            cached_providers = await cache_manager.get_dict(cache_key)
            if cached_providers:
                logger.debug(f"Retrieved {len(cached_providers)} providers from cache for tenant {tenant_id}")
                return cached_providers
            
            async with get_db_context() as db_session:
                providers = await self.load_tenant_providers_from_db(tenant_id, db_session)
                
                if providers:
                    await cache_manager.set_dict(
                        cache_key,
                        providers
                    )
                
                return providers
            
        except Exception as e:
            logger.error(f"Failed to get tenant providers: {e}")
            return {}
    
    async def get_tenant_agents(self, tenant_id: str) -> Dict[str, Any]:
        """
        Get tenant agents with caching
        """
        try:
            await self._ensure_initialized()
            
            cache_key = f"tenant:{tenant_id}:agents"
            
            cached_agents = await cache_manager.get_dict(cache_key)
            if cached_agents:
                logger.debug(f"Retrieved {len(cached_agents)} agents from cache for tenant {tenant_id}")
                return cached_agents
            
            async with get_db_context() as db_session:
                agents = await self.load_tenant_agents_from_db(tenant_id, db_session)
                
                if agents:
                    await cache_manager.set_dict(
                        cache_key,
                        agents
                    )
                
                return agents
            
        except Exception as e:
            logger.error(f"Failed to get tenant agents: {e}")
            return {}
    
    async def get_tenant_tools(self, tenant_id: str) -> Dict[str, Any]:
        """
        Get tenant tools with caching
        """
        try:
            await self._ensure_initialized()
            
            cache_key = f"tenant:{tenant_id}:tools"
            
            cached_tools = await cache_manager.get_dict(cache_key)
            if cached_tools:
                logger.debug(f"Retrieved {len(cached_tools)} tools from cache for tenant {tenant_id}")
                return cached_tools
            
            async with get_db_context() as db_session:
                tools = await self.load_tenant_tools_from_db(tenant_id, db_session)
                
                if tools:
                    await cache_manager.set_dict(
                        cache_key,
                        tools
                    )
                
                return tools
            
        except Exception as e:
            logger.error(f"Failed to get tenant tools: {e}")
            return {}
    
    async def get_tenant_workflow(self, tenant_id: str) -> Dict[str, Any]:
        """
        Get tenant workflow configuration with caching
        """
        try:
            await self._ensure_initialized()
            
            cache_key = f"tenant:{tenant_id}:workflows"
            
            cached_workflow = await cache_manager.get_dict(cache_key)
            if cached_workflow:
                logger.debug(f"Retrieved workflow config from cache for tenant {tenant_id}")
                return cached_workflow
            
            async with get_db_context() as db_session:
                workflow = await self.load_tenant_workflow_from_db(tenant_id, db_session)
                
                if workflow:
                    await cache_manager.set_dict(
                        cache_key,
                        workflow
                    )
                
                return workflow
            
        except Exception as e:
            logger.error(f"Failed to get tenant workflow: {e}")
            return {}
    
    async def invalidate_tenant_cache(self, tenant_id: str):
        """
        Invalidate all cached data for a tenant
        """
        try:
            await self._ensure_initialized()
            
            cache_patterns = [
                f"tenant:{tenant_id}:providers",
                f"tenant:{tenant_id}:agents",
                f"tenant:{tenant_id}:tools",
                f"tenant:{tenant_id}:workflows",
                f"tenant:{tenant_id}:permissions"
            ]
            
            for pattern in cache_patterns:
                await cache_manager.delete(pattern)
            
            await cache_manager.delete_pattern(f"tenant:{tenant_id}:user_permissions:*")
            
            logger.info(f"Invalidated cache for tenant {tenant_id}")
            
        except Exception as e:
            logger.error(f"Failed to invalidate tenant cache: {e}")
    
    async def get_tenant_cache_key(self, tenant_id: str, cache_type: str) -> str:
        """Get Redis key for tenant cache"""
        return f"tenant:{tenant_id}:{cache_type}"
    
    async def refresh_tenant_cache(self, tenant_id: str):
        """
        Refresh all tenant cache by loading fresh data from database
        """
        try:
            await self._ensure_initialized()
            
            async with get_db_context() as db_session:
                providers = await self.load_tenant_providers_from_db(tenant_id, db_session)
                if providers:
                    await cache_manager.set_dict(
                        f"tenant:{tenant_id}:providers",
                        providers
                    )
                
                agents = await self.load_tenant_agents_from_db(tenant_id, db_session)
                if agents:
                    await cache_manager.set_dict(
                        f"tenant:{tenant_id}:agents",
                        agents
                    )
                
                tools = await self.load_tenant_tools_from_db(tenant_id, db_session)
                if tools:
                    await cache_manager.set_dict(
                        f"tenant:{tenant_id}:tools",
                        tools
                    )
                
                workflow = await self.load_tenant_workflow_from_db(tenant_id, db_session)
                if workflow:
                    await cache_manager.set_dict(
                        f"tenant:{tenant_id}:workflows",
                        workflow
                    )
            
            logger.info(f"Refreshed all cache for tenant {tenant_id} (providers, agents, tools, workflow)")
            
        except Exception as e:
            logger.error(f"Failed to refresh tenant cache: {e}")
    
    @property
    def settings(self) -> Settings:
        """Get current settings"""
        return self._current_settings or Settings()
    
    async def get_monitoring_status(self) -> Dict[str, Any]:
        """Get monitoring status"""
        return {
            "initialized": self._initialized,
            "monitoring": self._monitoring,
            "last_update": self._last_update,
            "cache_initialized": cache_manager.is_initialized if hasattr(cache_manager, 'is_initialized') else False,
            "redis_initialized": redis_client.is_connected if hasattr(redis_client, 'is_connected') else False
        }


config_manager = ConfigManager()