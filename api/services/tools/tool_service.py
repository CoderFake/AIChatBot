from typing import Dict, List, Optional, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from utils.datetime_utils import CustomDateTime as datetime

from models.database.tool import Tool, DepartmentToolConfig
from models.database.tenant import Department
from tools.tool_registry import tool_registry
from utils.logging import get_logger

logger = get_logger(__name__)


class ToolService:
    """
    Tool service for database-driven tool management.
    - Get tool list from database
    - Update tool configuration
    - Enable/Disable tools for departments
    - Sync tool registry with database on startup
    """
    
    def __init__(self, db_session: AsyncSession):
        self.db = db_session
        self._tool_cache: Dict[str, Dict[str, Any]] = {}
        self._cache_timestamp: Optional[datetime] = None
        self._cache_ttl = 300  # 5 minutes
        self._initialized = False
    
    async def initialize(self):
        """Initialize tool service and sync registry with database."""
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
        Sync tool registry with database.
        Create database entries for tools that don't exist.
        """
        try:
            tool_registry.initialize()
            registry_tools = tool_registry.get_all_tool_info()
            
            result = await self.db.execute(select(Tool))
            existing_tools = {tool.tool_name: tool for tool in result.scalars().all()}
            
            tools_added = 0
            for tool_name, tool_info in registry_tools.items():
                if tool_name not in existing_tools:
                    new_tool = Tool(
                        tool_name=tool_name,
                        description=tool_info["description"],
                        category=tool_info["category"],
                        implementation_class=f"tools.{tool_info['category']}.{tool_name}",
                        is_enabled=True,
                        is_system=True, 
                        base_config={
                            "requires_permissions": tool_info["requires_permissions"],
                            "department_configurable": tool_info["department_configurable"]
                        }
                    )
                    
                    self.db.add(new_tool)
                    tools_added += 1
                    logger.debug(f"Added tool to database: {tool_name}")
            
            if tools_added > 0:
                await self.db.commit()
                logger.info(f"Synced {tools_added} tools from registry to database")
            
        except Exception as e:
            logger.error(f"Failed to sync registry to database: {e}")
            await self.db.rollback()
            raise
    
    def _is_cache_valid(self) -> bool:
        """Check if tool cache is still valid."""
        if not self._cache_timestamp:
            return False
        return (datetime.now() - self._cache_timestamp).seconds < self._cache_ttl
    
    async def _refresh_tool_cache(self):
        """Refresh tool cache from database."""
        try:
            result = await self.db.execute(
                select(Tool)
                .where(Tool.is_enabled == True)
                .order_by(Tool.tool_name)
            )
            
            tools = result.scalars().all()
            self._tool_cache = {}
            
            for tool in tools:
                dept_configs_result = await self.db.execute(
                    select(DepartmentToolConfig, Department)
                    .join(Department, DepartmentToolConfig.department_id == Department.id)
                    .where(DepartmentToolConfig.tool_id == tool.id)
                )
                
                department_configs = {}
                for dept_config, department in dept_configs_result:
                    department_configs[str(department.id)] = {
                        "department_name": department.department_name,
                        "is_enabled": dept_config.is_enabled,
                        "config_data": dept_config.config_data or {},
                        "usage_limits": dept_config.usage_limits or {},
                        "configured_by": str(dept_config.configured_by) if dept_config.configured_by else None
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
                    "department_configs": department_configs,
                    "registry_instance": tool_registry.get_tool(tool.tool_name)
                }
            
            self._cache_timestamp = datetime.now()
            logger.info(f"Tool cache refreshed with {len(self._tool_cache)} tools")
            
        except Exception as e:
            logger.error(f"Failed to refresh tool cache: {e}")
            if not self._tool_cache:
                self._tool_cache = {}
    
    async def get_all_tools(self) -> Dict[str, Dict[str, Any]]:
        """Get all tools from database with department configurations."""
        if not self._is_cache_valid():
            await self._refresh_tool_cache()
        
        return self._tool_cache.copy()
    
    async def get_tool_by_id(self, tool_id: str) -> Optional[Dict[str, Any]]:
        """Get specific tool by ID."""
        if not self._is_cache_valid():
            await self._refresh_tool_cache()
        
        return self._tool_cache.get(tool_id)
    
    async def get_tools_by_category(self, category: str) -> Dict[str, Dict[str, Any]]:
        """Get all tools in a specific category."""
        if not self._is_cache_valid():
            await self._refresh_tool_cache()
        
        return {
            tool_id: tool_info for tool_id, tool_info in self._tool_cache.items()
            if tool_info.get("category") == category
        }
    
    async def get_department_tools(self, department_id: str) -> Dict[str, Dict[str, Any]]:
        """Get all tools enabled for a specific department."""
        if not self._is_cache_valid():
            await self._refresh_tool_cache()
        
        department_tools = {}
        for tool_id, tool_info in self._tool_cache.items():
            dept_configs = tool_info.get("department_configs", {})
            
            # Check if tool is enabled for this department
            if department_id in dept_configs:
                dept_config = dept_configs[department_id]
                if dept_config.get("is_enabled", False):
                    department_tools[tool_id] = tool_info.copy()
            else:
                # If no specific config, check if tool is globally enabled
                if tool_info.get("is_enabled", False):
                    department_tools[tool_id] = tool_info.copy()
        
        return department_tools
    
    async def update_tool_status(self, tool_id: str, is_enabled: bool) -> bool:
        """Enable/disable a tool globally."""
        try:
            result = await self.db.execute(
                select(Tool).where(Tool.id == tool_id)
            )
            tool = result.scalar_one_or_none()
            
            if not tool:
                logger.warning(f"Tool {tool_id} not found")
                return False
            
            tool.is_enabled = is_enabled
            await self.db.commit()
            
            # Invalidate cache
            self._cache_timestamp = None
            
            logger.info(f"Updated tool {tool.tool_name} status to {is_enabled}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to update tool {tool_id}: {e}")
            await self.db.rollback()
            return False
    
    async def configure_department_tool(
        self,
        tool_id: str,
        department_id: str,
        is_enabled: bool,
        config_data: Optional[Dict[str, Any]] = None,
        usage_limits: Optional[Dict[str, Any]] = None,
        configured_by: Optional[str] = None
    ) -> bool:
        """Configure tool for specific department."""
        try:
            # Check if configuration already exists
            result = await self.db.execute(
                select(DepartmentToolConfig).where(
                    and_(
                        DepartmentToolConfig.tool_id == tool_id,
                        DepartmentToolConfig.department_id == department_id
                    )
                )
            )
            
            existing_config = result.scalar_one_or_none()
            
            if existing_config:
                # Update existing configuration
                existing_config.is_enabled = is_enabled
                existing_config.config_data = config_data or {}
                existing_config.usage_limits = usage_limits or {}
                existing_config.configured_by = configured_by
                
            else:
                # Create new configuration
                new_config = DepartmentToolConfig(
                    tool_id=tool_id,
                    department_id=department_id,
                    is_enabled=is_enabled,
                    config_data=config_data or {},
                    usage_limits=usage_limits or {},
                    configured_by=configured_by
                )
                self.db.add(new_config)
            
            await self.db.commit()
            
            # Invalidate cache
            self._cache_timestamp = None
            
            logger.info(f"Configured tool {tool_id} for department {department_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to configure tool {tool_id} for department {department_id}: {e}")
            await self.db.rollback()
            return False
    
    async def get_tool_statistics(self) -> Dict[str, Any]:
        """Get comprehensive tool statistics."""
        try:
            if not self._is_cache_valid():
                await self._refresh_tool_cache()
            
            # Basic counts
            total_tools = len(self._tool_cache)
            enabled_tools = len([t for t in self._tool_cache.values() if t.get("is_enabled")])
            
            # Category breakdown
            categories = {}
            for tool_info in self._tool_cache.values():
                category = tool_info.get("category", "uncategorized")
                categories[category] = categories.get(category, 0) + 1
            
            # Department usage
            department_usage = {}
            for tool_info in self._tool_cache.values():
                dept_configs = tool_info.get("department_configs", {})
                for dept_id, dept_config in dept_configs.items():
                    if dept_config.get("is_enabled"):
                        dept_name = dept_config.get("department_name", dept_id)
                        department_usage[dept_name] = department_usage.get(dept_name, 0) + 1
            
            # Registry sync status
            registry_tools_count = len(tool_registry.get_all_tools())
            
            return {
                "total_tools": total_tools,
                "enabled_tools": enabled_tools,
                "disabled_tools": total_tools - enabled_tools,
                "categories": categories,
                "department_usage": department_usage,
                "registry_tools_count": registry_tools_count,
                "cache_valid": self._is_cache_valid(),
                "initialized": self._initialized
            }
            
        except Exception as e:
            logger.error(f"Failed to get tool statistics: {e}")
            return {}
    
    def invalidate_cache(self):
        """Force cache refresh on next request."""
        self._cache_timestamp = None
        logger.info("Tool cache invalidated")
    
    async def health_check(self) -> bool:
        """Check tool service health."""
        try:
            if not self._initialized:
                return False
            
            # Test database connection
            result = await self.db.execute(select(Tool).limit(1))
            result.scalar_one_or_none()
            
            # Test registry
            registry_available = tool_registry.is_tool_available("calculator")
            
            return registry_available
            
        except Exception as e:
            logger.error(f"Tool service health check failed: {e}")
            return False