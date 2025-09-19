"""
Tool Service
Database-driven tool management for maintenance operations
"""
from typing import Dict, List, Optional, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, update, delete
from utils.datetime_utils import CustomDateTime as datetime
from utils.datetime_utils import DateTimeManager

from models.database.tool import Tool, TenantToolConfig
from models.database.tenant import Tenant
from tools.tool_registry import tool_registry
from utils.logging import get_logger

logger = get_logger(__name__)


class ToolService:
    """
    Tool service for database-driven tool management
    Handles maintenance operations across all tenants
    """
    
    def __init__(self, db_session: AsyncSession):
        self.db = db_session
        self._tool_cache: Dict[str, Dict[str, Any]] = {}
        self._cache_timestamp: Optional[datetime] = None
        self._cache_ttl = 300
        self._initialized = False
    
    async def initialize(self):
        """Initialize tool service and sync registry with database"""
        try:
            await self._sync_registry_to_database()
            await self._refresh_tool_cache()
            self._initialized = True
            logger.info("Tool service initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize tool service: {e}")
            raise
    
    async def _sync_registry_to_database(self):
        """
        Sync tool registry with database
        Creates database entries for new tools, sets is_enabled=False by default
        """
        try:
            tool_registry.initialize()
            registry_tools = tool_registry.get_all_tool_info()
            
            result = await self.db.execute(select(Tool))
            existing_tools = {tool.tool_name: tool for tool in result.scalars().all()}
            
            tools_added = 0
            tools_updated = 0
            
            for tool_name, tool_info in registry_tools.items():
                if tool_name not in existing_tools:
                    new_tool = Tool(
                        tool_name=tool_name,
                        description=tool_info["description"],
                        category=tool_info["category"],
                        implementation_class=tool_info["implementation_class"],
                        is_enabled=True,
                        is_system=True,
                        base_config={
                            "requires_permissions": tool_info["requires_permissions"],
                            "department_configurable": tool_info["department_configurable"]
                        }
                    )
                    
                    self.db.add(new_tool)
                    tools_added += 1
                    logger.info(f"Added new tool to database: {tool_name} (disabled by default)")
                    
                else:
                    existing_tool = existing_tools[tool_name]
                    existing_tool.description = tool_info["description"]
                    existing_tool.category = tool_info["category"]
                    existing_tool.implementation_class = tool_info["implementation_class"]
                    existing_tool.base_config = {
                        "requires_permissions": tool_info["requires_permissions"],
                        "department_configurable": tool_info["department_configurable"]
                    }
                    tools_updated += 1
                    logger.debug(f"Updated tool metadata: {tool_name}")
            
            if tools_added > 0 or tools_updated > 0:
                await self.db.commit()
                logger.info(f"Registry sync completed - Added: {tools_added}, Updated: {tools_updated}")
            
        except Exception as e:
            logger.error(f"Failed to sync registry to database: {e}")
            await self.db.rollback()
            raise
    
    def _is_cache_valid(self) -> bool:
        """Check if tool cache is still valid"""
        if not self._cache_timestamp:
            return False
        return (DateTimeManager._now() - self._cache_timestamp).seconds < self._cache_ttl
    
    async def _refresh_tool_cache(self):
        """Refresh tool cache from database (tenant-level only)"""
        try:
            result = await self.db.execute(
                select(Tool).order_by(Tool.tool_name)
            )
            
            tools = result.scalars().all()
            self._tool_cache = {}
            
            for tool in tools:
                tenant_configs_result = await self.db.execute(
                    select(TenantToolConfig, Tenant)
                    .join(Tenant, TenantToolConfig.tenant_id == Tenant.id)
                    .where(TenantToolConfig.tool_id == tool.id)
                )
                tenant_configs = {}
                for t_config, tenant in tenant_configs_result:
                    tenant_configs[str(t_config.tenant_id)] = {
                        "config_id": str(t_config.id),
                        "tenant_name": tenant.tenant_name,
                        "is_enabled": t_config.is_enabled,
                        "config_data": t_config.config_data or {},
                        "usage_limits": t_config.usage_limits or {},
                        "configured_by": str(t_config.configured_by) if t_config.configured_by else None,
                        "configured_at": t_config.created_at
                    }
                
                self._tool_cache[str(tool.id)] = {
                    "tool_id": str(tool.id),
                    "tool_name": tool.tool_name,
                    "description": tool.description,
                    "category": tool.category,
                    "implementation_class": tool.implementation_class,
                    "is_enabled": tool.is_enabled,
                    "is_system": tool.is_system,
                    "base_config": tool.base_config or {},
                    "tenant_configs": tenant_configs,
                    "created_at": tool.created_at,
                    "updated_at": tool.updated_at
                }
            
            self._cache_timestamp = DateTimeManager._now()
            logger.info(f"Tool cache refreshed with {len(self._tool_cache)} tools")
            
        except Exception as e:
            logger.error(f"Failed to refresh tool cache: {e}")
            if not self._tool_cache:
                self._tool_cache = {}
    
    async def get_all_tools(self) -> List[Dict[str, Any]]:
        """
        Get all tools with their configurations
        """
        try:
            if not self._is_cache_valid():
                await self._refresh_tool_cache()
            
            return list(self._tool_cache.values())
            
        except Exception as e:
            logger.error(f"Failed to get all tools: {e}")
            return []
    
    async def get_tool_by_id(self, tool_id: str) -> Optional[Dict[str, Any]]:
        """
        Get specific tool by ID
        """
        try:
            if not self._is_cache_valid():
                await self._refresh_tool_cache()
            
            return self._tool_cache.get(tool_id)
            
        except Exception as e:
            logger.error(f"Failed to get tool by ID: {e}")
            return None
    
    async def enable_tool_globally(self, tool_id: str) -> bool:
        """
        Enable tool globally (affects all tenants)
        """
        try:
            result = await self.db.execute(
                select(Tool).where(Tool.id == tool_id)
            )
            tool = result.scalar_one_or_none()
            
            if not tool:
                logger.warning(f"Tool not found: {tool_id}")
                return False
            
            tool.is_enabled = True
            tool.updated_at = DateTimeManager._now()
            
            await self.db.commit()
            await self._refresh_tool_cache()
            
            logger.info(f"Tool enabled globally: {tool.tool_name}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to enable tool globally: {e}")
            await self.db.rollback()
            return False
    
    async def disable_tool_globally(self, tool_id: str) -> bool:
        """
        Disable tool globally (affects all tenants)
        """
        try:
            result = await self.db.execute(
                select(Tool).where(Tool.id == tool_id)
            )
            tool = result.scalar_one_or_none()
            
            if not tool:
                logger.warning(f"Tool not found: {tool_id}")
                return False
            
            tool.is_enabled = False
            tool.updated_at = DateTimeManager._now()
            
            await self.db.commit()
            await self._refresh_tool_cache()
            
            logger.info(f"Tool disabled globally: {tool.tool_name}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to disable tool globally: {e}")
            await self.db.rollback()
            return False
    
    # Tenant-level APIs
    async def configure_tool_for_tenant(
        self,
        tool_id: str,
        tenant_id: str,
        is_enabled: bool,
        config_data: Optional[Dict[str, Any]] = None,
        usage_limits: Optional[Dict[str, Any]] = None,
        configured_by: Optional[str] = None
    ) -> bool:
        """Configure tool for specific tenant (preferred policy)."""
        try:
            result = await self.db.execute(
                select(TenantToolConfig)
                .where(
                    and_(
                        TenantToolConfig.tool_id == tool_id,
                        TenantToolConfig.tenant_id == tenant_id
                    )
                )
            )
            t_config = result.scalar_one_or_none()
            if t_config:
                t_config.is_enabled = is_enabled
                t_config.config_data = config_data or t_config.config_data
                t_config.usage_limits = usage_limits or t_config.usage_limits
                t_config.configured_by = configured_by or t_config.configured_by
                t_config.updated_at = DateTimeManager._now()
            else:
                t_config = TenantToolConfig(
                    tenant_id=tenant_id,
                    tool_id=tool_id,
                    is_enabled=is_enabled,
                    config_data=config_data or {},
                    usage_limits=usage_limits or {},
                    configured_by=configured_by
                )
                self.db.add(t_config)
            
            await self.db.commit()
            await self._refresh_tool_cache()
            logger.info(f"Tool {'enabled' if is_enabled else 'disabled'} for tenant: tool_id={tool_id}, tenant_id={tenant_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to configure tool for tenant: {e}")
            await self.db.rollback()
            return False

    async def get_tenant_tools(self, tenant_id: str) -> List[Dict[str, Any]]:
        """Get all tools for specific tenant using cache."""
        try:
            if not self._is_cache_valid():
                await self._refresh_tool_cache()
            
            tenant_tools: List[Dict[str, Any]] = []
            for tool_id, tool_info in self._tool_cache.items():
                if not tool_info.get("is_enabled", False):
                    continue
                t_configs = tool_info.get("tenant_configs", {})
                t_config = t_configs.get(tenant_id, {})
                
                tenant_tools.append({
                    "tool_id": tool_id,
                    "tool_name": tool_info["tool_name"],
                    "description": tool_info["description"],
                    "category": tool_info["category"],
                    "is_enabled_globally": tool_info["is_enabled"],
                    "is_enabled_for_tenant": t_config.get("is_enabled", False),
                    "config_data": t_config.get("config_data", {}),
                    "usage_limits": t_config.get("usage_limits", {}),
                    "base_config": tool_info.get("base_config", {}),
                    "configured_at": t_config.get("configured_at")
                })
            return tenant_tools
        except Exception as e:
            logger.error(f"Failed to get tenant tools: {e}")
            return []

    async def delete_tool(self, tool_id: str) -> bool:
        """
        Delete tool (only non-system tools)
        """
        try:
            result = await self.db.execute(
                select(Tool).where(Tool.id == tool_id)
            )
            tool = result.scalar_one_or_none()
            
            if not tool:
                logger.warning(f"Tool not found: {tool_id}")
                return False
            
            if tool.is_system:
                logger.warning(f"Cannot delete system tool: {tool.tool_name}")
                return False
            
            await self.db.execute(
                delete(TenantToolConfig).where(TenantToolConfig.tool_id == tool_id)
            )
            
            await self.db.delete(tool)
            await self.db.commit()
            await self._refresh_tool_cache()
            
            logger.info(f"Tool deleted: {tool.tool_name}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to delete tool: {e}")
            await self.db.rollback()
            return False
    
    async def get_tool_usage_stats(self, tool_id: str) -> Dict[str, Any]:
        """
        Get tool usage statistics across tenants
        """
        try:
            if not self._is_cache_valid():
                await self._refresh_tool_cache()
            
            tool_info = self._tool_cache.get(tool_id)
            if not tool_info:
                return {}
            
            tenant_configs = tool_info.get("tenant_configs", {})
            
            stats = {
                "tool_id": tool_id,
                "tool_name": tool_info["tool_name"],
                "total_tenants": len(tenant_configs),
                "enabled_tenants": sum(1 for config in tenant_configs.values() if config.get("is_enabled", False)),
                "disabled_tenants": sum(1 for config in tenant_configs.values() if not config.get("is_enabled", False)),
                "tenant_details": tenant_configs,
            }
            
            return stats
            
        except Exception as e:
            logger.error(f"Failed to get tool usage stats: {e}")
            return {}
    
    async def invalidate_cache(self):
        """Force cache refresh"""
        try:
            await self._refresh_tool_cache()
            logger.info("Tool service cache invalidated and refreshed")
            
        except Exception as e:
            logger.error(f"Failed to invalidate cache: {e}")
            raise

    # ==================== MAINTAINER-ONLY METHODS ====================

    async def create_tool(
        self,
        tool_name: str,
        description: str,
        tool_type: str,
        config_schema: Optional[Dict[str, Any]] = None,
        is_system: bool = False
    ) -> Dict[str, Any]:
        """Create a new tool (MAINTAINER only)"""
        try:
            tool = Tool(
                tool_name=tool_name,
                description=description,
                category=tool_type,
                implementation_class=f"tools.{tool_name}_tool.{tool_name.title()}Tool",
                is_enabled=False,  # Disabled by default
                is_system=is_system,
                base_config=config_schema or {},
                config_schema=config_schema or {}
            )

            self.db.add(tool)
            await self.db.commit()
            await self.db.refresh(tool)

            # Invalidate cache
            self._cache_timestamp = None

            logger.info(f"Created new tool: {tool_name} with ID: {tool.id}")

            return {
                "id": str(tool.id),
                "tool_name": tool_name,
                "description": description,
                "category": tool_type,
                "is_enabled": False,
                "is_system": is_system,
                "created_at": tool.created_at.isoformat() if tool.created_at else None
            }

        except Exception as e:
            logger.error(f"Failed to create tool {tool_name}: {e}")
            await self.db.rollback()
            raise

    async def update_tool(
        self,
        tool_id: str,
        tool_name: Optional[str] = None,
        description: Optional[str] = None,
        tool_type: Optional[str] = None,
        config_schema: Optional[Dict[str, Any]] = None,
        is_enabled: Optional[bool] = None
    ) -> bool:
        """Update tool configuration (MAINTAINER only)"""
        try:
            result = await self.db.execute(select(Tool).where(Tool.id == tool_id))
            tool = result.scalar_one_or_none()

            if not tool:
                return False

            if tool_name:
                tool.tool_name = tool_name
            if description:
                tool.description = description
            if tool_type:
                tool.category = tool_type
            if config_schema is not None:
                tool.config_schema = config_schema
            if is_enabled is not None:
                tool.is_enabled = is_enabled

            await self.db.commit()

            # Invalidate cache
            self._cache_timestamp = None

            logger.info(f"Updated tool {tool_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to update tool {tool_id}: {e}")
            await self.db.rollback()
            return False

    async def delete_tool_cascade(self, tool_id: str) -> bool:
        """Delete tool and cascade delete related configurations (MAINTAINER only)"""
        try:
            # Get tool first
            result = await self.db.execute(select(Tool).where(Tool.id == tool_id))
            tool = result.scalar_one_or_none()

            if not tool:
                return False

            # Prevent deletion of system tools
            if tool.is_system:
                logger.error(f"Cannot delete system tool: {tool.tool_name}")
                return False

            await self.db.execute(
                delete(TenantToolConfig).where(TenantToolConfig.tool_id == tool_id)
            )

            from models.database.agent import AgentToolConfig
            await self.db.execute(
                delete(AgentToolConfig).where(AgentToolConfig.tool_id == tool_id)
            )

            await self.db.execute(delete(Tool).where(Tool.id == tool_id))

            await self.db.commit()

            self._cache_timestamp = None

            logger.info(f"Deleted tool {tool_id} with cascade")
            return True

        except Exception as e:
            logger.error(f"Failed to delete tool {tool_id} with cascade: {e}")
            await self.db.rollback()
            return False

    async def get_all_tools_with_tenant_configs(self) -> List[Dict[str, Any]]:
        """Get all tools across all tenants with their configurations (MAINTAINER only)"""
        try:
            # Get all tools
            result = await self.db.execute(select(Tool))
            tools = result.scalars().all()

            tool_list = []
            for tool in tools:
                tenant_configs_result = await self.db.execute(
                    select(TenantToolConfig, Tenant)
                    .join(Tenant, TenantToolConfig.tenant_id == Tenant.id)
                    .where(TenantToolConfig.tool_id == tool.id)
                )

                tenant_configs = {}
                for config, tenant in tenant_configs_result:
                    tenant_configs[str(tenant.id)] = {
                        "tenant_name": tenant.tenant_name,
                        "is_enabled": config.is_enabled,
                        "config_data": config.config_data or {},
                        "created_at": config.created_at.isoformat() if config.created_at else None,
                        "updated_at": config.updated_at.isoformat() if config.updated_at else None
                    }

                tool_list.append({
                    "id": str(tool.id),
                    "tool_name": tool.tool_name,
                    "description": tool.description,
                    "category": tool.category,
                    "is_enabled": tool.is_enabled,
                    "is_system": tool.is_system,
                    "base_config": tool.base_config or {},
                    "config_schema": tool.config_schema or {},
                    "tenant_configs": tenant_configs,
                    "total_tenants": len(tenant_configs),
                    "enabled_tenants": sum(1 for config in tenant_configs.values() if config["is_enabled"]),
                    "created_at": tool.created_at.isoformat() if tool.created_at else None,
                    "updated_at": tool.updated_at.isoformat() if tool.updated_at else None
                })

            return tool_list

        except Exception as e:
            logger.error(f"Failed to get all tools with tenant configs: {e}")
            return []

    async def remove_tool_from_tenant(self, tool_id: str, tenant_id: str) -> bool:
        """Remove tool from a tenant (MAINTAINER only)"""
        try:
            result = await self.db.execute(
                select(TenantToolConfig).where(
                    and_(
                        TenantToolConfig.tool_id == tool_id,
                        TenantToolConfig.tenant_id == tenant_id
                    )
                )
            )
            config = result.scalar_one_or_none()

            if not config:
                return False

            await self.db.execute(
                delete(TenantToolConfig).where(
                    and_(
                        TenantToolConfig.tool_id == tool_id,
                        TenantToolConfig.tenant_id == tenant_id
                    )
                )
            )

            await self.db.commit()

            self._cache_timestamp = None

            logger.info(f"Removed tool {tool_id} from tenant {tenant_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to remove tool {tool_id} from tenant {tenant_id}: {e}")
            await self.db.rollback()
            return False

    async def get_tools_for_tenant_admin(self, tenant_id: str) -> List[Dict[str, Any]]:
        """
        Get tools for tenant admin with their tenant configurations
        """
        try:
            result = await self.db.execute(
                select(Tool, TenantToolConfig).outerjoin(
                    TenantToolConfig,
                    (TenantToolConfig.tool_id == Tool.id) & (TenantToolConfig.tenant_id == tenant_id)
                ).where(Tool.is_enabled == True)
            )

            tools_data = result.all()
            response = []

            for tool, tenant_config in tools_data:
                is_enabled = tenant_config.is_enabled if tenant_config else True

                response.append({
                    "id": str(tool.id),
                    "tool_name": tool.tool_name,
                    "description": tool.description,
                    "category": tool.category,
                    "is_enabled": is_enabled,
                    "is_system": tool.is_system,
                    "access_level": tool.access_level
                })

            return response

        except Exception as e:
            logger.error(f"Failed to get tools for tenant admin: {e}")
            raise

    async def enable_tool_for_tenant(self, tool_id: str, tenant_id: str, is_enabled: bool = True) -> str:
        """
        Enable or disable tool for tenant
        """
        try:
            tool_result = await self.db.execute(
                select(Tool).where(Tool.id == tool_id, Tool.is_enabled == True)
            )
            tool = tool_result.scalar_one_or_none()

            if not tool:
                raise ValueError("Tool not found")

            config_result = await self.db.execute(
                select(TenantToolConfig).where(
                    TenantToolConfig.tenant_id == tenant_id,
                    TenantToolConfig.tool_id == tool_id
                )
            )
            tenant_config = config_result.scalar_one_or_none()

            if tenant_config:
                tenant_config.is_enabled = is_enabled
            else:
                tenant_config = TenantToolConfig(
                    tenant_id=tenant_id,
                    tool_id=tool_id,
                    is_enabled=is_enabled
                )
                self.db.add(tenant_config)

            await self.db.commit()

            self._cache_timestamp = None

            action = "enabled" if is_enabled else "disabled"
            return f"Tool {action} successfully"

        except Exception as e:
            logger.error(f"Failed to enable/disable tool {tool_id} for tenant {tenant_id}: {e}")
            await self.db.rollback()
            raise

    async def enable_tool_for_department(
        self,
        department_id: str,
        tool_id: str,
        tenant_id: str,
        is_enabled: bool = True,
        access_level_override: Optional[str] = None
    ) -> str:
        """
        Enable or disable tool for department (DEPT_ADMIN or higher)
        """
        try:
            from models.database.tenant import Department
            dept_result = await self.db.execute(
                select(Department).where(
                    Department.id == department_id,
                    Department.tenant_id == tenant_id,
                    Department.is_deleted == False
                )
            )
            department = dept_result.scalar_one_or_none()

            if not department:
                raise ValueError("Department not found")

            from models.database.tool import Tool, TenantToolConfig
            tool_result = await self.db.execute(
                select(Tool, TenantToolConfig).outerjoin(
                    TenantToolConfig,
                    (TenantToolConfig.tool_id == Tool.id) & (TenantToolConfig.tenant_id == tenant_id)
                ).where(
                    Tool.id == tool_id,
                    Tool.is_enabled == True
                )
            )
            tool_data = tool_result.first()

            if not tool_data or (tool_data[1] and not tool_data[1].is_enabled):
                raise ValueError("Tool not available for this tenant")

            from models.database.agent import AgentToolConfig, Agent
            from models.database.tenant import Department

            agents_result = await self.db.execute(
                select(Agent).where(Agent.department_id == department_id)
            )
            department_agents = agents_result.scalars().all()

            if not department_agents:
                raise ValueError(f"No agents found in department {department_id}")

            updated_configs = []
            for agent in department_agents:
                config_result = await self.db.execute(
                    select(AgentToolConfig).where(
                        AgentToolConfig.agent_id == agent.id,
                        AgentToolConfig.tool_id == tool_id
                    )
                )
                agent_config = config_result.scalar_one_or_none()

                if agent_config:
                    agent_config.is_enabled = is_enabled
                    if access_level_override:
                        agent_config.access_level_override = access_level_override
                    config = agent_config
                else:
                    config = AgentToolConfig(
                        agent_id=agent.id,
                        tool_id=tool_id,
                        is_enabled=is_enabled,
                        access_level_override=access_level_override
                )
                self.db.add(config)

                updated_configs.append({
                    "agent_id": str(agent.id),
                    "agent_name": agent.agent_name,
                    "config_id": str(config.id)
                })

            await self.db.commit()

            self._cache_timestamp = None

            action = "enabled" if is_enabled else "disabled"
            return f"Tool {action} for {len(updated_configs)} agents in department successfully"

        except Exception as e:
            logger.error(f"Failed to enable/disable tool {tool_id} for department {department_id}: {e}")
            await self.db.rollback()
            raise