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
                    department_configs[str(department.id)] = {
                        "department_name": department.department_name,
                        "is_enabled": dept_config.is_enabled,
                        "config_data": dept_config.config_data or {},
                        "usage_limits": dept_config.usage_limits or {},
                        "configured_by": str(dept_config.configured_by) if dept_config.configured_by else None,
                        "configured_at": dept_config.configured_at
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
    
    async def get_all_tools(self, include_disabled: bool = False) -> Dict[str, Dict[str, Any]]:
        """Get all tools from database with optional filtering"""
        if not self._is_cache_valid():
            await self._refresh_tool_cache()
        
        if include_disabled:
            return self._tool_cache.copy()
        else:
            return {
                tool_id: tool_info 
                for tool_id, tool_info in self._tool_cache.items()
                if tool_info.get("is_enabled", False)
            }
    
    async def get_tool_by_id(self, tool_id: str) -> Optional[Dict[str, Any]]:
        """Get specific tool by ID"""
        if not self._is_cache_valid():
            await self._refresh_tool_cache()
        
        return self._tool_cache.get(tool_id)
    
    async def get_tool_by_name(self, tool_name: str) -> Optional[Dict[str, Any]]:
        """Get specific tool by name"""
        if not self._is_cache_valid():
            await self._refresh_tool_cache()
        
        for tool_info in self._tool_cache.values():
            if tool_info.get("tool_name") == tool_name:
                return tool_info
        return None
    
    async def enable_tool(self, tool_id: str, enabled_by: str) -> bool:
        """Enable a tool system-wide (maintenance operation)"""
        try:
            result = await self.db.execute(
                update(Tool)
                .where(Tool.id == tool_id)
                .values(
                    is_enabled=True,
                    updated_at=datetime.now()
                )
                .returning(Tool.tool_name)
            )
            
            tool_name = result.scalar_one_or_none()
            if tool_name:
                await self.db.commit()
                self.invalidate_cache()
                logger.info(f"Tool enabled: {tool_name} (ID: {tool_id}) by {enabled_by}")
                return True
            else:
                logger.warning(f"Tool not found for enabling: {tool_id}")
                return False
                
        except Exception as e:
            logger.error(f"Failed to enable tool {tool_id}: {e}")
            await self.db.rollback()
            return False
    
    async def disable_tool(self, tool_id: str, disabled_by: str) -> bool:
        """Disable a tool system-wide (maintenance operation)"""
        try:
            result = await self.db.execute(
                update(Tool)
                .where(Tool.id == tool_id)
                .values(
                    is_enabled=False,
                    updated_at=datetime.now()
                )
                .returning(Tool.tool_name)
            )
            
            tool_name = result.scalar_one_or_none()
            if tool_name:
                await self.db.commit()
                self.invalidate_cache()
                logger.info(f"Tool disabled: {tool_name} (ID: {tool_id}) by {disabled_by}")
                return True
            else:
                logger.warning(f"Tool not found for disabling: {tool_id}")
                return False
                
        except Exception as e:
            logger.error(f"Failed to disable tool {tool_id}: {e}")
            await self.db.rollback()
            return False
    
    async def update_tool_config(self, tool_id: str, base_config: Dict[str, Any], updated_by: str) -> bool:
        """Update tool base configuration (maintenance operation)"""
        try:
            result = await self.db.execute(
                update(Tool)
                .where(Tool.id == tool_id)
                .values(
                    base_config=base_config,
                    updated_at=datetime.now()
                )
                .returning(Tool.tool_name)
            )
            
            tool_name = result.scalar_one_or_none()
            if tool_name:
                await self.db.commit()
                self.invalidate_cache()
                logger.info(f"Tool config updated: {tool_name} (ID: {tool_id}) by {updated_by}")
                return True
            else:
                logger.warning(f"Tool not found for config update: {tool_id}")
                return False
                
        except Exception as e:
            logger.error(f"Failed to update tool config {tool_id}: {e}")
            await self.db.rollback()
            return False
    
    
    async def enable_tool_for_department(
        self, 
        tool_id: str, 
        department_id: str, 
        config_data: Optional[Dict[str, Any]] = None,
        usage_limits: Optional[Dict[str, Any]] = None,
        configured_by: str = None
    ) -> bool:
        """Enable tool for specific department"""
        try:
            tool_info = await self.get_tool_by_id(tool_id)
            if not tool_info:
                logger.warning(f"Tool not found: {tool_id}")
                return False
            
            if not tool_info.get("is_enabled"):
                logger.warning(f"Tool is system-disabled: {tool_info.get('tool_name')}")
                return False
            
            existing_config = await self.db.execute(
                select(DepartmentToolConfig)
                .where(
                    and_(
                        DepartmentToolConfig.tool_id == tool_id,
                        DepartmentToolConfig.department_id == department_id
                    )
                )
            )
            
            dept_config = existing_config.scalar_one_or_none()
            
            if dept_config:
                dept_config.is_enabled = True
                dept_config.config_data = config_data or dept_config.config_data
                dept_config.usage_limits = usage_limits or dept_config.usage_limits
                dept_config.configured_by = configured_by
                dept_config.configured_at = datetime.now()
            else:
                dept_config = DepartmentToolConfig(
                    tool_id=tool_id,
                    department_id=department_id,
                    is_enabled=True,
                    config_data=config_data or {},
                    usage_limits=usage_limits or {},
                    configured_by=configured_by,
                    configured_at=datetime.now()
                )
                self.db.add(dept_config)
            
            await self.db.commit()
            self.invalidate_cache()
            
            logger.info(f"Tool {tool_info.get('tool_name')} enabled for department {department_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to enable tool {tool_id} for department {department_id}: {e}")
            await self.db.rollback()
            return False
    
    async def disable_tool_for_department(self, tool_id: str, department_id: str, disabled_by: str) -> bool:
        """Disable tool for specific department"""
        try:
            result = await self.db.execute(
                update(DepartmentToolConfig)
                .where(
                    and_(
                        DepartmentToolConfig.tool_id == tool_id,
                        DepartmentToolConfig.department_id == department_id
                    )
                )
                .values(
                    is_enabled=False,
                    configured_by=disabled_by,
                    configured_at=datetime.now()
                )
            )
            
            if result.rowcount > 0:
                await self.db.commit()
                self.invalidate_cache()
                logger.info(f"Tool {tool_id} disabled for department {department_id}")
                return True
            else:
                logger.warning(f"Department tool config not found: tool={tool_id}, dept={department_id}")
                return False
                
        except Exception as e:
            logger.error(f"Failed to disable tool {tool_id} for department {department_id}: {e}")
            await self.db.rollback()
            return False
    
    async def get_department_tools(self, department_id: str) -> Dict[str, Dict[str, Any]]:
        """Get all enabled tools for a specific department"""
        if not self._is_cache_valid():
            await self._refresh_tool_cache()
        
        department_tools = {}
        for tool_id, tool_info in self._tool_cache.items():
            if not tool_info.get("is_enabled"):
                continue
            
            dept_configs = tool_info.get("department_configs", {})
            dept_config = dept_configs.get(department_id)
            
            if dept_config and dept_config.get("is_enabled"):
                department_tools[tool_id] = {
                    **tool_info,
                    "department_config": dept_config
                }
            elif not dept_config and not tool_info.get("base_config", {}).get("department_configurable", False):
                department_tools[tool_id] = tool_info
        
        return department_tools
    
    async def get_tool_statistics(self) -> Dict[str, Any]:
        """Get comprehensive tool statistics"""
        try:
            if not self._is_cache_valid():
                await self._refresh_tool_cache()
            
            total_tools = len(self._tool_cache)
            enabled_tools = len([t for t in self._tool_cache.values() if t.get("is_enabled")])
            
            categories = {}
            for tool_info in self._tool_cache.values():
                category = tool_info.get("category", "uncategorized")
                categories[category] = categories.get(category, 0) + 1
            
            department_usage = {}
            total_dept_configs = 0
            
            for tool_info in self._tool_cache.values():
                dept_configs = tool_info.get("department_configs", {})
                total_dept_configs += len(dept_configs)
                
                for dept_id, dept_config in dept_configs.items():
                    if dept_config.get("is_enabled"):
                        dept_name = dept_config.get("department_name", f"Department {dept_id}")
                        department_usage[dept_name] = department_usage.get(dept_name, 0) + 1
            
            registry_tools_count = len(tool_registry.get_all_tool_info())
            registry_stats = tool_registry.get_registry_stats()
            
            return {
                "total_tools": total_tools,
                "enabled_tools": enabled_tools,
                "disabled_tools": total_tools - enabled_tools,
                "categories": categories,
                "department_usage": department_usage,
                "total_department_configs": total_dept_configs,
                "registry_tools_count": registry_tools_count,
                "registry_stats": registry_stats,
                "cache_valid": self._is_cache_valid(),
                "initialized": self._initialized
            }
            
        except Exception as e:
            logger.error(f"Failed to get tool statistics: {e}")
            return {}
    
    def invalidate_cache(self):
        """Force cache refresh on next request"""
        self._cache_timestamp = None
        logger.info("Tool cache invalidated")
    
    async def health_check(self) -> bool:
        """Check tool service health"""
        try:
            if not self._initialized:
                return False
            
            result = await self.db.execute(select(Tool).limit(1))
            result.scalar_one_or_none()
            
            registry_available = tool_registry.is_tool_available("calculator")
            
            return registry_available
            
        except Exception as e:
            logger.error(f"Tool service health check failed: {e}")
            return False