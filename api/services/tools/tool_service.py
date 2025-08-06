"""
Tool Service
Database-driven tool management for maintenance operations
"""
from typing import Dict, List, Optional, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, update, delete
from utils.datetime_utils import CustomDateTime as datetime

from models.database.tool import Tool, DepartmentToolConfig
from models.database.tenant import Department
from api.tools.tool_registry import tool_registry
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
                        is_enabled=False,
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
        return (datetime.now() - self._cache_timestamp).seconds < self._cache_ttl
    
    async def _refresh_tool_cache(self):
        """Refresh tool cache from database"""
        try:
            result = await self.db.execute(
                select(Tool).order_by(Tool.tool_name)
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
                    department_configs[str(dept_config.department_id)] = {
                        "config_id": str(dept_config.id),
                        "department_name": department.department_name,
                        "is_enabled": dept_config.is_enabled,
                        "config_data": dept_config.config_data or {},
                        "usage_limits": dept_config.usage_limits or {},
                        "configured_by": str(dept_config.configured_by) if dept_config.configured_by else None,
                        "configured_at": dept_config.created_at
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
                    "created_at": tool.created_at,
                    "updated_at": tool.updated_at
                }
            
            self._cache_timestamp = datetime.now()
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
        Enable tool globally (affects all departments)
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
            tool.updated_at = datetime.now()
            
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
        Disable tool globally (affects all departments)
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
            tool.updated_at = datetime.now()
            
            await self.db.commit()
            await self._refresh_tool_cache()
            
            logger.info(f"Tool disabled globally: {tool.tool_name}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to disable tool globally: {e}")
            await self.db.rollback()
            return False
    
    async def configure_tool_for_department(
        self,
        tool_id: str,
        department_id: str,
        is_enabled: bool,
        config_data: Optional[Dict[str, Any]] = None,
        usage_limits: Optional[Dict[str, Any]] = None,
        configured_by: Optional[str] = None
    ) -> bool:
        """
        Configure tool for specific department
        """
        try:
            result = await self.db.execute(
                select(DepartmentToolConfig)
                .where(
                    and_(
                        DepartmentToolConfig.tool_id == tool_id,
                        DepartmentToolConfig.department_id == department_id
                    )
                )
            )
            
            dept_config = result.scalar_one_or_none()
            
            if dept_config:
                dept_config.is_enabled = is_enabled
                dept_config.config_data = config_data or dept_config.config_data
                dept_config.usage_limits = usage_limits or dept_config.usage_limits
                dept_config.configured_by = configured_by or dept_config.configured_by
                dept_config.updated_at = datetime.now()
            else:
                dept_config = DepartmentToolConfig(
                    department_id=department_id,
                    tool_id=tool_id,
                    is_enabled=is_enabled,
                    config_data=config_data or {},
                    usage_limits=usage_limits or {},
                    configured_by=configured_by
                )
                self.db.add(dept_config)
            
            await self.db.commit()
            await self._refresh_tool_cache()
            
            action = "enabled" if is_enabled else "disabled"
            logger.info(f"Tool {action} for department: tool_id={tool_id}, dept_id={department_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to configure tool for department: {e}")
            await self.db.rollback()
            return False
    
    async def get_department_tools(self, department_id: str) -> List[Dict[str, Any]]:
        """
        Get all tools available for specific department
        """
        try:
            if not self._is_cache_valid():
                await self._refresh_tool_cache()
            
            department_tools = []
            
            for tool_id, tool_info in self._tool_cache.items():
                if not tool_info.get("is_enabled", False):
                    continue
                
                dept_configs = tool_info.get("department_configs", {})
                dept_config = dept_configs.get(department_id, {})
                
                tool_data = {
                    "tool_id": tool_id,
                    "tool_name": tool_info["tool_name"],
                    "description": tool_info["description"],
                    "category": tool_info["category"],
                    "is_enabled_globally": tool_info["is_enabled"],
                    "is_enabled_for_department": dept_config.get("is_enabled", False),
                    "config_data": dept_config.get("config_data", {}),
                    "usage_limits": dept_config.get("usage_limits", {}),
                    "base_config": tool_info.get("base_config", {}),
                    "configured_at": dept_config.get("configured_at")
                }
                
                department_tools.append(tool_data)
            
            return department_tools
            
        except Exception as e:
            logger.error(f"Failed to get department tools: {e}")
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
                delete(DepartmentToolConfig).where(DepartmentToolConfig.tool_id == tool_id)
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
        Get tool usage statistics across departments
        """
        try:
            if not self._is_cache_valid():
                await self._refresh_tool_cache()
            
            tool_info = self._tool_cache.get(tool_id)
            if not tool_info:
                return {}
            
            dept_configs = tool_info.get("department_configs", {})
            
            stats = {
                "tool_id": tool_id,
                "tool_name": tool_info["tool_name"],
                "total_departments": len(dept_configs),
                "enabled_departments": sum(1 for config in dept_configs.values() if config.get("is_enabled", False)),
                "disabled_departments": sum(1 for config in dept_configs.values() if not config.get("is_enabled", False)),
                "department_details": dept_configs
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