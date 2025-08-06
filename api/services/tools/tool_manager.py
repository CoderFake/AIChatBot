# api/services/tools/tool_manager.py
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
                            self._tool_instances[tool_id] = tool_instance
                            logger.debug(f"Initialized tool instance: {tool_name}")
                        else:
                            logger.warning(f"Tool not found in registry: {tool_name}")
                    except Exception as e:
                        logger.error(f"Failed to initialize tool {tool_name}: {e}")
            
            logger.info(f"Initialized {len(self._tool_instances)} tool instances")
            
        except Exception as e:
            logger.error(f"Failed to initialize tool instances: {e}")
            raise
    
    async def get_tools_for_department(self, department_id: str) -> List[Dict[str, Any]]:
        """
        Get available tools for a specific department
        Returns list of tools with department-specific configurations
        """
        try:
            if not self._is_cache_valid():
                await self._refresh_tool_cache()
            
            department_tools = []
            
            for tool_id, tool_info in self._tool_cache.items():
                dept_configs = tool_info.get("department_configs", {})
                
                if department_id in dept_configs:
                    dept_config = dept_configs[department_id]
                    
                    if dept_config.get("is_enabled", False):
                        tool_data = {
                            "tool_id": tool_id,
                            "tool_name": tool_info["tool_name"],
                            "description": tool_info["description"],
                            "category": tool_info["category"],
                            "config": {
                                **tool_info.get("base_config", {}),
                                **dept_config.get("config_data", {})
                            },
                            "usage_limits": dept_config.get("usage_limits", {}),
                            "instance": self._tool_instances.get(tool_id)
                        }
                        department_tools.append(tool_data)
            
            logger.debug(f"Found {len(department_tools)} tools for department {department_id}")
            return department_tools
            
        except Exception as e:
            logger.error(f"Failed to get tools for department: {e}")
            return []
    
    async def get_tool_instance(self, tool_id: str, department_id: str) -> Optional[Any]:
        """
        Get tool instance for specific department
        Returns None if tool not available for department
        """
        try:
            if not self._is_cache_valid():
                await self._refresh_tool_cache()
            
            tool_info = self._tool_cache.get(tool_id)
            if not tool_info:
                return None
            
            dept_configs = tool_info.get("department_configs", {})
            if department_id not in dept_configs:
                return None
            
            dept_config = dept_configs[department_id]
            if not dept_config.get("is_enabled", False):
                return None
            
            return self._tool_instances.get(tool_id)
            
        except Exception as e:
            logger.error(f"Failed to get tool instance: {e}")
            return None
    
    async def get_tool_config(self, tool_id: str, department_id: str) -> Dict[str, Any]:
        """
        Get tool configuration for specific department
        Merges base config with department-specific config
        """
        try:
            if not self._is_cache_valid():
                await self._refresh_tool_cache()
            
            tool_info = self._tool_cache.get(tool_id, {})
            dept_configs = tool_info.get("department_configs", {})
            dept_config = dept_configs.get(department_id, {})
            
            base_config = tool_info.get("base_config", {})
            dept_specific_config = dept_config.get("config_data", {})
            
            merged_config = {**base_config, **dept_specific_config}
            
            return {
                "config": merged_config,
                "usage_limits": dept_config.get("usage_limits", {}),
                "is_enabled": dept_config.get("is_enabled", False)
            }
            
        except Exception as e:
            logger.error(f"Failed to get tool config: {e}")
            return {"config": {}, "usage_limits": {}, "is_enabled": False}
    
    async def check_tool_availability(self, tool_name: str, department_id: str) -> bool:
        """
        Check if tool is available for department
        """
        try:
            if not self._is_cache_valid():
                await self._refresh_tool_cache()
            
            for tool_id, tool_info in self._tool_cache.items():
                if tool_info.get("tool_name") == tool_name:
                    dept_configs = tool_info.get("department_configs", {})
                    dept_config = dept_configs.get(department_id, {})
                    return dept_config.get("is_enabled", False)
            
            return False
            
        except Exception as e:
            logger.error(f"Failed to check tool availability: {e}")
            return False
    
    async def get_all_tools(self) -> Dict[str, Dict[str, Any]]:
        """
        Get all tools in cache
        For administrative purposes
        """
        try:
            if not self._is_cache_valid():
                await self._refresh_tool_cache()
            
            return self._tool_cache.copy()
            
        except Exception as e:
            logger.error(f"Failed to get all tools: {e}")
            return {}
    
    async def invalidate_cache(self):
        """Force cache refresh"""
        try:
            await self._refresh_tool_cache()
            await self._initialize_tool_instances()
            logger.info("Tool cache invalidated and refreshed")
            
        except Exception as e:
            logger.error(f"Failed to invalidate cache: {e}")
            raise


tool_manager = ToolManager()