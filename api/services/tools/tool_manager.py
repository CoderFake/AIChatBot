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
from utils.logging import get_logger
from config.database import get_db_context

logger = get_logger(__name__)


class ToolManager:
    """
    Database-driven tool manager using IDs instead of codes
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
                            "is_enabled": dept_config.is_enabled,
                            "config_data": dept_config.config_data or {},
                            "usage_limits": dept_config.usage_limits or {}
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
                logger.info(f"Tool cache refreshed with {len(self._tool_cache)} tools")
                
        except Exception as e:
            logger.error(f"Failed to refresh tool cache: {e}")
            if not self._tool_cache:
                self._tool_cache = {}
    
    async def _initialize_tool_instances(self):
        """Initialize tool instances based on implementation classes"""
        try:
            for tool_id, tool_info in self._tool_cache.items():
                implementation_class = tool_info.get("implementation_class")
                
                if implementation_class:
                    try:
                        module_path, class_name = implementation_class.rsplit('.', 1)
                        module = __import__(module_path, fromlist=[class_name])
                        tool_class = getattr(module, class_name)
                        
                        base_config = tool_info.get("base_config", {})
                        tool_instance = tool_class(base_config)
                        
                        self._tool_instances[tool_id] = tool_instance
                        logger.debug(f"Initialized tool instance for {tool_info['tool_name']} (ID: {tool_id})")
                        
                    except Exception as e:
                        logger.warning(f"Failed to initialize tool {tool_info['tool_name']} (ID: {tool_id}): {e}")
                else:
                    logger.debug(f"No implementation class for tool {tool_info['tool_name']} (ID: {tool_id})")
            
            logger.info(f"Initialized {len(self._tool_instances)} tool instances")
            
        except Exception as e:
            logger.error(f"Failed to initialize tool instances: {e}")
    
    async def get_available_tools(self, department_id: Optional[str] = None) -> Dict[str, Dict[str, Any]]:
        """Get available tools, optionally filtered by department"""
        if not self._is_cache_valid():
            await self._refresh_tool_cache()
        
        if not department_id:
            return self._tool_cache.copy()
        
        department_tools = {}
        for tool_id, tool_info in self._tool_cache.items():
            dept_configs = tool_info.get("department_configs", {})
            if department_id in dept_configs and dept_configs[department_id].get("is_enabled"):
                department_tools[tool_id] = tool_info.copy()
        
        return department_tools
    
    async def get_tool_by_id(self, tool_id: str) -> Optional[Dict[str, Any]]:
        """Get specific tool by ID"""
        if not self._is_cache_valid():
            await self._refresh_tool_cache()
        
        return self._tool_cache.get(tool_id)
    
    async def get_tool_config(self, tool_id: str, department_id: Optional[str] = None) -> Dict[str, Any]:
        """Get complete tool configuration for specific department"""
        tool_info = await self.get_tool_by_id(tool_id)
        if not tool_info:
            return {}
        
        config = {
            "tool_id": tool_id,
            "tool_name": tool_info["tool_name"],
            "category": tool_info["category"],
            "base_config": tool_info.get("base_config", {})
        }
        
        if department_id:
            dept_configs = tool_info.get("department_configs", {})
            if department_id in dept_configs:
                dept_config = dept_configs[department_id]
                config.update({
                    "config_data": dept_config.get("config_data", {}),
                    "usage_limits": dept_config.get("usage_limits", {}),
                    "is_enabled": dept_config.get("is_enabled", False)
                })
        
        return config
    
    async def execute_tool(
        self,
        tool_id: str,
        tool_name: str,
        query: str,
        user_context: Dict[str, Any],
        agent_config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Execute tool by ID"""
        try:
            if not self._initialized:
                await self.initialize()
            
            department_id = user_context.get("department_id")
            tool_config = await self.get_tool_config(tool_id, department_id)
            
            if not tool_config:
                raise ValueError(f"Tool {tool_id} not found or not configured")
            
            tool_instance = self._tool_instances.get(tool_id)
            if not tool_instance:
                raise ValueError(f"Tool instance for {tool_id} not available")
            
            if not tool_config.get("is_enabled", False):
                raise ValueError(f"Tool {tool_name} is not enabled for this department")
            
            execution_context = {
                "query": query,
                "user_context": user_context,
                "agent_config": agent_config,
                "tool_config": tool_config
            }
            
            if hasattr(tool_instance, 'execute'):
                result = await tool_instance.execute(execution_context)
            elif hasattr(tool_instance, '__call__'):
                result = await tool_instance(execution_context)
            else:
                raise ValueError(f"Tool {tool_name} does not have execute method")
            
            logger.info(f"Tool {tool_name} (ID: {tool_id}) executed successfully")
            return result
            
        except Exception as e:
            logger.error(f"Tool execution failed for {tool_name} (ID: {tool_id}): {e}")
            return {
                "error": str(e),
                "tool_id": tool_id,
                "tool_name": tool_name,
                "status": "failed"
            }
    
    async def is_tool_available(self, tool_id: str, department_id: Optional[str] = None) -> bool:
        """Check if tool is available for use"""
        tool_config = await self.get_tool_config(tool_id, department_id)
        return bool(tool_config and tool_config.get("is_enabled", False))
    
    async def get_tools_by_category(self, category: str, department_id: Optional[str] = None) -> Dict[str, Dict[str, Any]]:
        """Get tools filtered by category"""
        available_tools = await self.get_available_tools(department_id)
        
        return {
            tool_id: tool_info for tool_id, tool_info in available_tools.items()
            if tool_info.get("category") == category
        }
    
    async def create_tool(
        self,
        tool_name: str,
        description: str,
        category: str,
        implementation_class: Optional[str] = None,
        base_config: Optional[Dict[str, Any]] = None,
        is_system: bool = False
    ) -> Optional[str]:
        """Create new tool in database"""
        try:
            async with get_db_context() as db:
                tool = Tool(
                    tool_name=tool_name,
                    description=description,
                    category=category,
                    implementation_class=implementation_class,
                    base_config=base_config or {},
                    is_system=is_system,
                    is_enabled=True
                )
                
                db.add(tool)
                db.commit()
                db.refresh(tool)
                
                self._cache_timestamp = None
                
                logger.info(f"Created tool: {tool_name} with ID: {tool.id}")
                return str(tool.id)
                
        except Exception as e:
            logger.error(f"Failed to create tool {tool_name}: {e}")
            return None
    
    async def update_tool_status(self, tool_id: str, is_enabled: bool) -> bool:
        """Enable/disable tool"""
        try:
            async with get_db_context() as db:
                tool = db.query(Tool).filter(Tool.id == tool_id).first()
                if not tool:
                    return False
                
                tool.is_enabled = is_enabled
                db.commit()
                
                self._cache_timestamp = None
                
                logger.info(f"Updated tool {tool_id} status to {is_enabled}")
                return True
                
        except Exception as e:
            logger.error(f"Failed to update tool {tool_id}: {e}")
            return False
    
    async def configure_tool_for_department(
        self,
        tool_id: str,
        department_id: str,
        is_enabled: bool = True,
        config_data: Optional[Dict[str, Any]] = None,
        usage_limits: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Configure tool for specific department"""
        try:
            async with get_db_context() as db:
                existing_config = (
                    db.query(DepartmentToolConfig)
                    .filter(
                        and_(
                            DepartmentToolConfig.tool_id == tool_id,
                            DepartmentToolConfig.department_id == department_id
                        )
                    )
                    .first()
                )
                
                if existing_config:
                    existing_config.is_enabled = is_enabled
                    existing_config.config_data = config_data or {}
                    existing_config.usage_limits = usage_limits or {}
                else:
                    new_config = DepartmentToolConfig(
                        tool_id=tool_id,
                        department_id=department_id,
                        is_enabled=is_enabled,
                        config_data=config_data or {},
                        usage_limits=usage_limits or {}
                    )
                    db.add(new_config)
                
                db.commit()
                
                self._cache_timestamp = None
                
                logger.info(f"Configured tool {tool_id} for department {department_id}")
                return True
                
        except Exception as e:
            logger.error(f"Failed to configure tool {tool_id} for department {department_id}: {e}")
            return False
    
    async def get_tool_stats(self) -> Dict[str, Any]:
        """Get tool statistics"""
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
            
            return {
                "total_tools": total_tools,
                "enabled_tools": enabled_tools,
                "disabled_tools": total_tools - enabled_tools,
                "category_stats": category_stats,
                "initialized_instances": initialized_instances,
                "cache_status": "valid" if self._is_cache_valid() else "invalid"
            }
            
        except Exception as e:
            logger.error(f"Failed to get tool stats: {e}")
            return {}
    
    def invalidate_cache(self):
        """Force cache refresh on next request"""
        self._cache_timestamp = None
        logger.info("Tool cache invalidated")
    
    async def health_check(self) -> bool:
        """Check tool manager health"""
        try:
            if not self._initialized:
                return False
            
            await self._refresh_tool_cache()
            return True
            
        except Exception as e:
            logger.error(f"Tool manager health check failed: {e}")
            return False


tool_manager = ToolManager()