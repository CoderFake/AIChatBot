"""
Tool Manager Service
Database-driven tool management with ID-based operations
"""
from typing import Dict, Any, List, Optional
from sqlalchemy import and_
from datetime import datetime
import json

from models.database.tool import Tool, DepartmentToolConfig
from models.database.tenant import Department
from api.tools.tool_registry import tool_registry
from utils.logging import get_logger
from config.database import get_db_context

logger = get_logger(__name__)


class ToolManager:
    """
    Runtime tool manager that receives tools from tool_registry and syncs with database
    Handles tool instances and runtime operations
    """
    
    def __init__(self):
        self._tool_cache: Dict[str, Dict[str, Any]] = {}
        self._tool_instances: Dict[str, Any] = {}
        self._cache_timestamp: Optional[datetime] = None
        self._cache_ttl = 300
        self._initialized = False
    
    async def initialize(self):
        """Initialize tool manager and load tools from database"""
        try:
            await self._refresh_tool_cache()
            await self._initialize_tool_instances()
            self._initialized = True
            logger.info("Tool manager initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize tool manager: {e}")
            raise
    
    def _is_cache_valid(self) -> bool:
        """Check if tool cache is still valid"""
        if not self._cache_timestamp:
            return False
        return (datetime.now() - self._cache_timestamp).seconds < self._cache_ttl
    
    async def _refresh_tool_cache(self):
        """Refresh tool cache from database"""
        try:
            async with get_db_context() as db:
                tools = (
                    db.query(Tool)
                    .filter(Tool.is_enabled == True)
                    .all()
                )
                
                self._tool_cache = {}
                
                for tool in tools:
                    dept_configs = (
                        db.query(DepartmentToolConfig)
                        .join(Department)
                        .filter(
                            and_(
                                DepartmentToolConfig.tool_id == tool.id,
                                DepartmentToolConfig.is_enabled == True
                            )
                        )
                        .all()
                    )
                    
                    department_configs = {}
                    for dept_config in dept_configs:
                        department_configs[str(dept_config.department_id)] = {
                            "config_id": str(dept_config.id),
                            "department_name": dept_config.department.department_name,
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
                        "department_configs": department_configs
                    }
                
                self._cache_timestamp = datetime.now()
                logger.info(f"Tool cache refreshed with {len(self._tool_cache)} enabled tools")
                
        except Exception as e:
            logger.error(f"Failed to refresh tool cache: {e}")
            if not self._tool_cache:
                self._tool_cache = {}
    
    async def _initialize_tool_instances(self):
        """Initialize tool instances from registry based on database configuration"""
        try:
            tool_registry.initialize()
            
            for tool_id, tool_info in self._tool_cache.items():
                tool_name = tool_info.get("tool_name")
                implementation_class = tool_info.get("implementation_class")
                
                if implementation_class:
                    try:
                        tool_instance = tool_registry.get_tool(tool_name)
                        
                        if tool_instance:
                            self._tool_instances[tool_id] = {
                                "instance": tool_instance,
                                "tool_name": tool_name,
                                "category": tool_info.get("category"),
                                "base_config": tool_info.get("base_config", {}),
                                "department_configs": tool_info.get("department_configs", {})
                            }
                            logger.debug(f"Initialized tool instance: {tool_name}")
                        else:
                            logger.warning(f"Tool instance not found in registry: {tool_name}")
                            
                    except Exception as e:
                        logger.error(f"Failed to initialize tool instance {tool_name}: {e}")
                        
            logger.info(f"Initialized {len(self._tool_instances)} tool instances")
            
        except Exception as e:
            logger.error(f"Failed to initialize tool instances: {e}")
    
    
    async def get_available_tools(self, department_id: Optional[str] = None) -> Dict[str, Any]:
        """Get available tools, optionally filtered by department"""
        if not self._is_cache_valid():
            await self._refresh_tool_cache()
        
        if not department_id:
            return {
                tool_id: {
                    "tool_name": info["tool_name"],
                    "description": info["description"],
                    "category": info["category"],
                    "instance": self._tool_instances.get(tool_id, {}).get("instance")
                }
                for tool_id, info in self._tool_cache.items()
                if tool_id in self._tool_instances
            }
        
        available_tools = {}
        for tool_id, tool_info in self._tool_cache.items():
            if tool_id not in self._tool_instances:
                continue
            
            dept_configs = tool_info.get("department_configs", {})
            base_config = tool_info.get("base_config", {})
            
            is_available = False
            tool_config = {}
            
            if department_id in dept_configs:
                dept_config = dept_configs[department_id]
                if dept_config.get("is_enabled"):
                    is_available = True
                    tool_config = dept_config.get("config_data", {})
            elif not base_config.get("department_configurable", False):
                is_available = True
                tool_config = base_config
            
            if is_available:
                available_tools[tool_id] = {
                    "tool_name": tool_info["tool_name"],
                    "description": tool_info["description"],
                    "category": tool_info["category"],
                    "config": tool_config,
                    "instance": self._tool_instances[tool_id]["instance"]
                }
        
        return available_tools
    
    async def get_tool_instance(self, tool_id: str, department_id: Optional[str] = None) -> Optional[Any]:
        """Get a specific tool instance if available for department"""
        if not self._is_cache_valid():
            await self._refresh_tool_cache()
        
        if tool_id not in self._tool_instances:
            return None
        
        tool_info = self._tool_cache.get(tool_id)
        if not tool_info:
            return None
        
        if department_id:
            dept_configs = tool_info.get("department_configs", {})
            base_config = tool_info.get("base_config", {})
            
            if department_id in dept_configs:
                dept_config = dept_configs[department_id]
                if not dept_config.get("is_enabled"):
                    return None
            elif base_config.get("department_configurable", False):
                return None
        
        return self._tool_instances[tool_id]["instance"]
    
    async def get_tool_by_name(self, tool_name: str, department_id: Optional[str] = None) -> Optional[Any]:
        """Get tool instance by name"""
        if not self._is_cache_valid():
            await self._refresh_tool_cache()
        
        for tool_id, tool_info in self._tool_cache.items():
            if tool_info.get("tool_name") == tool_name:
                return await self.get_tool_instance(tool_id, department_id)
        
        return None
    
    async def get_tools_by_category(self, category: str, department_id: Optional[str] = None) -> Dict[str, Any]:
        """Get all tools in a specific category for a department"""
        available_tools = await self.get_available_tools(department_id)
        
        return {
            tool_id: tool_info
            for tool_id, tool_info in available_tools.items()
            if tool_info.get("category") == category
        }
    
    async def execute_tool(
        self,
        tool_id: str,
        department_id: str,
        user_id: str,
        **kwargs
    ) -> Dict[str, Any]:
        """Execute a tool with proper access control"""
        try:

            tool_instance = await self.get_tool_instance(tool_id, department_id)
            if not tool_instance:
                return {
                    "success": False,
                    "error": "Tool not available or not enabled for department"
                }
            
            tool_info = self._tool_cache.get(tool_id, {})
            tool_name = tool_info.get("tool_name", "unknown")
            
            logger.info(f"Executing tool {tool_name} for user {user_id} in department {department_id}")
            
            if hasattr(tool_instance, 'run'):
                result = tool_instance.run(**kwargs)
            elif hasattr(tool_instance, 'invoke'):
                result = tool_instance.invoke(kwargs)
            else:
                return {
                    "success": False,
                    "error": "Tool does not have a valid execution method"
                }
            
            logger.info(f"Tool {tool_name} executed successfully")
            
            return {
                "success": True,
                "result": result,
                "tool_name": tool_name,
                "executed_by": user_id,
                "department_id": department_id
            }
            
        except Exception as e:
            logger.error(f"Tool execution failed: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def execute_tool_async(
        self,
        tool_id: str,
        department_id: str,
        user_id: str,
        **kwargs
    ) -> Dict[str, Any]:
        """Execute a tool asynchronously"""
        try:
            tool_instance = await self.get_tool_instance(tool_id, department_id)
            if not tool_instance:
                return {
                    "success": False,
                    "error": "Tool not available or not enabled for department"
                }
            
            tool_info = self._tool_cache.get(tool_id, {})
            tool_name = tool_info.get("tool_name", "unknown")
            
            logger.info(f"Executing tool {tool_name} async for user {user_id} in department {department_id}")
            
            if hasattr(tool_instance, 'arun'):
                result = await tool_instance.arun(**kwargs)
            elif hasattr(tool_instance, 'ainvoke'):
                result = await tool_instance.ainvoke(kwargs)
            elif hasattr(tool_instance, 'run'):
                result = tool_instance.run(**kwargs)
            else:
                return {
                    "success": False,
                    "error": "Tool does not have a valid execution method"
                }
            
            logger.info(f"Tool {tool_name} executed async successfully")
            
            return {
                "success": True,
                "result": result,
                "tool_name": tool_name,
                "executed_by": user_id,
                "department_id": department_id
            }
            
        except Exception as e:
            logger.error(f"Async tool execution failed: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def configure_tool_for_department(
        self,
        tool_id: str,
        department_id: str,
        config_data: Dict[str, Any],
        usage_limits: Optional[Dict[str, Any]] = None,
        configured_by: str = None
    ) -> bool:
        """Configure tool for department (handled by ToolService, but cache needs refresh)"""
        try:
            await self._refresh_tool_cache()
            await self._initialize_tool_instances()
            
            logger.info(f"Tool {tool_id} configuration refreshed for department {department_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to refresh tool configuration {tool_id} for department {department_id}: {e}")
            return False
    
    
    async def get_tool_stats(self) -> Dict[str, Any]:
        """Get tool statistics for monitoring"""
        try:
            if not self._is_cache_valid():
                await self._refresh_tool_cache()
            
            total_tools = len(self._tool_cache)
            enabled_tools = len([t for t in self._tool_cache.values() if t.get("is_enabled")])
            
            category_stats = {}
            for tool_info in self._tool_cache.values():
                category = tool_info.get("category", "unknown")
                if category not in category_stats:
                    category_stats[category] = 0
                category_stats[category] += 1
            
            initialized_instances = len(self._tool_instances)
            
            dept_usage = {}
            for tool_info in self._tool_cache.values():
                dept_configs = tool_info.get("department_configs", {})
                for dept_id, dept_config in dept_configs.items():
                    dept_name = dept_config.get("department_name", f"Dept {dept_id}")
                    if dept_name not in dept_usage:
                        dept_usage[dept_name] = 0
                    dept_usage[dept_name] += 1
            
            return {
                "total_tools": total_tools,
                "enabled_tools": enabled_tools,
                "disabled_tools": total_tools - enabled_tools,
                "category_stats": category_stats,
                "initialized_instances": initialized_instances,
                "department_usage": dept_usage,
                "cache_status": "valid" if self._is_cache_valid() else "invalid",
                "initialized": self._initialized
            }
            
        except Exception as e:
            logger.error(f"Failed to get tool stats: {e}")
            return {}
    
    def invalidate_cache(self):
        """Force cache refresh on next request"""
        self._cache_timestamp = None
        logger.info("Tool manager cache invalidated")
    
    async def health_check(self) -> bool:
        """Check tool manager health"""
        try:
            if not self._initialized:
                return False
            
            await self._refresh_tool_cache()
            
            registry_available = tool_registry.is_tool_available("calculator")
            
            instances_available = len(self._tool_instances) > 0
            
            return registry_available and instances_available
            
        except Exception as e:
            logger.error(f"Tool manager health check failed: {e}")
            return False


tool_manager = ToolManager()