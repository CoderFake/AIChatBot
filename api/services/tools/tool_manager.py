from typing import Dict, List, Any, Optional, Union, Annotated, Callable
from datetime import datetime
import asyncio
import json
import importlib
from dataclasses import dataclass

# LangGraph core imports
from langchain_core.tools import tool
from langchain_core.messages import ToolMessage, AIMessage
from langgraph.prebuilt import ToolNode

# Local imports
from config.settings import get_settings
from utils.logging import get_logger
from core.exceptions import ToolNotFoundError, ToolDisabledError, ServiceError
from services.dataclasses.tools import ToolUsageStats
from services.tools.tool_registry import tool_registry, ToolCategory
from services.tools.tools import get_tool_function, get_available_tools

logger = get_logger(__name__)
settings = get_settings()


class ToolManager:
    """
    Manager class cho LangGraph tools với dynamic registration
    Hỗ trợ agents đăng ký tools riêng của mình
    """
    
    def __init__(self):
        self.usage_stats: Dict[str, ToolUsageStats] = {}
        
        self._agent_tools: Dict[str, Dict[str, Callable]] = {}
        
        self._active_tools: Dict[str, Callable] = {}
        
        self._initialize_system_tools()
        
        self._initialize_tool_node()
    
    def _initialize_system_tools(self):
        """Khởi tạo system tools từ tools.py"""
        try:
            available_tools = get_available_tools()
            
            for tool_name, tool_func in available_tools.items():
                if self._is_tool_enabled(tool_name):
                    self._active_tools[tool_name] = tool_func
                    logger.debug(f"Loaded system tool: {tool_name}")
            
            logger.info(f"Initialized {len(self._active_tools)} system tools")
        
        except Exception as e:
            logger.error(f"Failed to initialize system tools: {e}")
    
    def _initialize_tool_node(self):
        """Initialize LangGraph ToolNode với active tools"""
        enabled_tools = []
        
        for tool_name, tool_func in self._active_tools.items():
            enabled_tools.append(tool_func)
            
            if tool_name not in self.usage_stats:
                self.usage_stats[tool_name] = ToolUsageStats(tool_name=tool_name)
        
        for agent_name, agent_tools in self._agent_tools.items():
            for tool_name, tool_func in agent_tools.items():
                if self._is_tool_enabled(tool_name):
                    enabled_tools.append(tool_func)
                    
                    # Initialize usage stats
                    if tool_name not in self.usage_stats:
                        self.usage_stats[tool_name] = ToolUsageStats(tool_name=tool_name)
        
        self.tool_node = ToolNode(enabled_tools) if enabled_tools else None
        logger.info(f"Initialized ToolNode with {len(enabled_tools)} tools")
    
    def _is_tool_enabled(self, tool_name: str) -> bool:
        tool_definition = tool_registry.get_tool_definition(tool_name)
        
        if tool_definition:
            settings_key = tool_definition.get("settings_key")
            if settings_key:
                return getattr(settings, settings_key, False)
            
            return True
       
        return True
    
    # ================================
    # AGENT TOOL REGISTRATION
    # ================================
    
    def register_tools_from_available(
        self,
        agent_name: str,
        tool_names: List[str],
        custom_configs: Optional[Dict[str, Dict[str, Any]]] = None
    ) -> Dict[str, bool]:
        
        results = {}
        available_tools = get_available_tools()
        
        for tool_name in tool_names:
            try:
                if tool_name not in available_tools:
                    logger.error(f"Tool {tool_name} is not in AVAILABLE_TOOLS")
                    results[tool_name] = False
                    continue
                
                tool_function = available_tools[tool_name]
                
                default_config = tool_registry.get_tool_definition(tool_name)
                
                tool_config = default_config.copy() if default_config else {}
                if custom_configs and tool_name in custom_configs:
                    tool_config.update(custom_configs[tool_name])
                
                success = self.register_agent_tool(
                    agent_name=agent_name,
                    tool_name=tool_name,
                    tool_function=tool_function,
                    tool_config=tool_config
                )
                
                results[tool_name] = success
        
            except Exception as e:
                logger.error(f"Failed to register tool {tool_name} for agent {agent_name}: {e}")
                results[tool_name] = False

        return results
    
    def list_available_tools_for_agent(self) -> Dict[str, Dict[str, Any]]:
        """
        Lấy danh sách tools có thể đăng ký từ AVAILABLE_TOOLS
        
    Returns:
            Dict chứa thông tin tools
        """
        available_tools = get_available_tools()
        tools_info = {}
        
        for tool_name, tool_func in available_tools.items():
            definition = tool_registry.get_tool_definition(tool_name)
            
            tools_info[tool_name] = {
                "function_name": tool_func.name if hasattr(tool_func, 'name') else tool_name,
                "description": tool_func.__doc__ or "No description",
                "category": definition.get("category") if definition else "utility_tools",
                "display_name": definition.get("display_name") if definition else tool_name.title(),
                "requirements": definition.get("requirements") if definition else {},
                "usage_limits": definition.get("usage_limits") if definition else {},
                "is_system": definition.get("is_system", False) if definition else False
            }
        
        return tools_info
    
    def register_agent_tool(
        self,
        agent_name: str,
        tool_name: str,
        tool_function: Callable,
        tool_config: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Đăng ký tool cho một agent cụ thể
        
        Args:
            agent_name: Tên agent đăng ký tool
            tool_name: Tên tool (unique trong scope của agent)
            tool_function: Function implement tool (phải có decorator @tool)
            tool_config: Config cho tool (metadata)
            
        Returns:
            bool: True nếu đăng ký thành công
        """
        try:
            # Validate tool function
            if not hasattr(tool_function, 'name'):
                logger.error(f"Tool function must have @tool decorator: {tool_name}")
                return False
            
            # Create agent namespace if not exists
            if agent_name not in self._agent_tools:
                self._agent_tools[agent_name] = {}
            
            # Generate unique tool name
            full_tool_name = f"{agent_name}_{tool_name}"
            
            # Check for conflicts
            if full_tool_name in self._active_tools:
                logger.warning(f"Tool {full_tool_name} already exists")
                return False
            
            # Register in agent tools
            self._agent_tools[agent_name][full_tool_name] = tool_function
            
            # Auto-register in tool registry if config provided
            if tool_config:
                success = tool_registry.register_tool(
                    name=full_tool_name,
                    display_name=tool_config.get("display_name", tool_name),
                    category=tool_config.get("category", ToolCategory.UTILITY_TOOLS.value),
                    description=tool_config.get("description", f"Tool {tool_name} của agent {agent_name}"),
                    implementation_class=f"agents.{agent_name}.tools.{tool_name}",
                    tool_config=tool_config.get("config", {}),
                    requirements=tool_config.get("requirements", {}),
                    usage_limits=tool_config.get("usage_limits", {}),
                    version=tool_config.get("version", "1.0.0"),
                    is_system=False,
                    departments_allowed=tool_config.get("departments_allowed"),
                    documentation_url=tool_config.get("documentation_url")
                )
                
                if not success:
                    logger.warning(f"Failed to register {full_tool_name} in tool registry")
            
            # Re-initialize tool node
            self._initialize_tool_node()
            
            logger.info(f"Agent {agent_name} registered tool: {full_tool_name}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to register agent tool {tool_name} for {agent_name}: {e}")
            return False

    def unregister_agent_tool(self, agent_name: str, tool_name: str) -> bool:
        """
            Hủy đăng ký tool của agent
        
        Args:
                agent_name: Tên agent
                tool_name: Tên tool
            
        Returns:
                bool: True nếu hủy thành công
        """
        try:
            full_tool_name = f"{agent_name}_{tool_name}"
            
            if agent_name not in self._agent_tools:
                logger.warning(f"Agent {agent_name} has no registered tools")
                return False
            
            if full_tool_name not in self._agent_tools[agent_name]:
                logger.warning(f"Tool {full_tool_name} not found for agent {agent_name}")
                return False
            
            # Remove from agent tools
            del self._agent_tools[agent_name][full_tool_name]
            
            # Remove from registry
            tool_registry.unregister_tool(full_tool_name)
            
            # Remove usage stats
            if full_tool_name in self.usage_stats:
                del self.usage_stats[full_tool_name]
            
            # Re-initialize tool node
            self._initialize_tool_node()
            
            logger.info(f"Unregistered tool {full_tool_name} from agent {agent_name}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to unregister agent tool {tool_name} for {agent_name}: {e}")
            return False
    
    def get_agent_tools(self, agent_name: str) -> List[str]:
        """
        Lấy danh sách tools của một agent
        
        Args:
            agent_name: Tên agent
            
        Returns:
            List[str]: Danh sách tên tools
        """
        if agent_name not in self._agent_tools:
            return []
        
        return list(self._agent_tools[agent_name].keys())
    
    def register_agent_tools_batch(
        self,
        agent_name: str,
        tools_config: Dict[str, Dict[str, Any]]
    ) -> Dict[str, bool]:
        """
        Đăng ký nhiều tools cho agent một lần
        
        Args:
            agent_name: Tên agent
            tools_config: Dict mapping tool_name -> config
            
        Returns:
            Dict[str, bool]: Kết quả đăng ký từng tool
        """
        results = {}
        
        for tool_name, config in tools_config.items():
            try:
                # Load tool function dynamically
                tool_function = self._load_agent_tool_function(agent_name, tool_name, config)
                
                if tool_function:
                    success = self.register_agent_tool(agent_name, tool_name, tool_function, config)
                    results[tool_name] = success
                else:
                    results[tool_name] = False
                    
            except Exception as e:
                logger.error(f"Failed to batch register tool {tool_name} for {agent_name}: {e}")
                results[tool_name] = False
        
        return results
    
    def _load_agent_tool_function(
        self, 
        agent_name: str, 
        tool_name: str, 
        config: Dict[str, Any]
    ) -> Optional[Callable]:
        """
        Dynamically load tool function từ agent module
        
        Args:
            agent_name: Tên agent
            tool_name: Tên tool
            config: Tool config
            
        Returns:
            Tool function hoặc None nếu load failed
        """
        try:
            # Construct module path
            module_path = config.get("module_path", f"agents.{agent_name}.tools")
            function_name = config.get("function_name", f"{tool_name}_tool")
            
            # Import module and get function
            module = importlib.import_module(module_path)
            tool_function = getattr(module, function_name, None)
            
            if not tool_function:
                logger.error(f"Function {function_name} not found in {module_path}")
                return None
            
            # Validate it's a proper tool
            if not hasattr(tool_function, 'name'):
                logger.error(f"Function {function_name} must have @tool decorator")
                return None
            
            return tool_function
            
        except ImportError as e:
            logger.error(f"Failed to import agent tool module {module_path}: {e}")
            return None
        except Exception as e:
            logger.error(f"Failed to load agent tool function: {e}")
            return None
    
    # ================================
    # TOOL EXECUTION
    # ================================
    
    async def invoke_tools(self, messages: List[AIMessage]) -> List[ToolMessage]:
        """
        Invoke tools using LangGraph ToolNode
        
        Args:
            messages: List of AI messages with tool calls
            
        Returns:
            List of tool messages with results
        """
        if not self.tool_node:
            raise ToolDisabledError("No tools are enabled")
        
        try:
            # Track usage
            for message in messages:
                if hasattr(message, 'tool_calls') and message.tool_calls:
                    for tool_call in message.tool_calls:
                        tool_name = tool_call.get('name', 'unknown')
                        self._update_usage_stats(tool_name, success=True)
            
            # Use LangGraph ToolNode to execute tools
            result = await self.tool_node.ainvoke({"messages": messages})
            return result.get("messages", [])
            
        except Exception as e:
            # Track failed usage
            for message in messages:
                if hasattr(message, 'tool_calls') and message.tool_calls:
                    for tool_call in message.tool_calls:
                        tool_name = tool_call.get('name', 'unknown')
                        self._update_usage_stats(tool_name, success=False)
            
            logger.error(f"Tool invocation error: {str(e)}")
            raise ServiceError(f"Error executing tools: {str(e)}")
    
    # ================================
    # DATABASE SYNC
    # ================================
    
    async def sync_tools_to_database(self, db_session):
        """
        Đồng bộ tools từ registry vào database
        """
        try:
            from sqlalchemy import select
            from models.database.tool import Tool
            from models.database.permission import Permission, ToolPermission
            
            sync_count = 0
            update_count = 0
            
            # Lấy definitions từ registry
            tool_definitions = tool_registry.get_all_tools()
            
            for tool_name, tool_def in tool_definitions.items():
                # Check tool đã tồn tại chưa
                existing_query = select(Tool).where(Tool.name == tool_name)
                result = await db_session.execute(existing_query)
                existing_tool = result.scalar_one_or_none()
                
                if existing_tool:
                    # Cập nhật nếu version khác
                    if existing_tool.version != tool_def["version"]:
                        existing_tool.version = tool_def["version"]
                        existing_tool.tool_config = tool_def["tool_config"]
                        existing_tool.requirements = tool_def["requirements"]
                        update_count += 1
                        logger.info(f"Updated tool {tool_name} to version {tool_def['version']}")
                else:
                    # Tạo tool mới
                    new_tool = Tool(
                        name=tool_name,
                        display_name=tool_def["display_name"],
                        description=tool_def["description"],
                        category=tool_def["category"],
                        implementation_class=tool_def["implementation_class"],
                        tool_config=tool_def["tool_config"],
                        requirements=tool_def["requirements"],
                        usage_limits=tool_def.get("usage_limits"),
                        version=tool_def["version"],
                        is_system=tool_def.get("is_system", True),
                        departments_allowed=tool_def.get("departments_allowed"),
                        documentation_url=tool_def.get("documentation_url")
                    )
                    
                    db_session.add(new_tool)
                    sync_count += 1
                    logger.info(f"Synced new tool to database: {tool_name}")
            
            await db_session.commit()
            logger.info(f"Tool sync completed: {sync_count} new tools, {update_count} updated tools")
            return {"synced": sync_count, "updated": update_count}
            
        except Exception as e:
            await db_session.rollback()
            logger.error(f"Failed to sync tools to database: {e}")
            return {"synced": 0, "updated": 0, "error": str(e)}
    
    # ================================
    # UTILITY METHODS
    # ================================
    
    def _update_usage_stats(self, tool_name: str, success: bool = True):
        """Update usage statistics for a tool"""
        if tool_name not in self.usage_stats:
            self.usage_stats[tool_name] = ToolUsageStats(tool_name=tool_name)
        
        stats = self.usage_stats[tool_name]
        stats.usage_count += 1
        
        if success:
            stats.success_count += 1
        else:
            stats.error_count += 1
            
        stats.last_used = datetime.now().isoformat()
    
    def get_enabled_tools(self) -> List[str]:
        """Get list of enabled tool names"""
        enabled_tools = []
        
        # System tools
        enabled_tools.extend([
            tool_name for tool_name in self._active_tools.keys()
            if self._is_tool_enabled(tool_name)
        ])
        
        # Agent tools
        for agent_name, agent_tools in self._agent_tools.items():
            enabled_tools.extend([
                tool_name for tool_name in agent_tools.keys()
                if self._is_tool_enabled(tool_name)
            ])
        
        return enabled_tools
    
    def get_tool_stats(self) -> Dict[str, Dict[str, Any]]:
        """Get usage statistics for all tools"""
        return {
            tool_name: {
                "usage_count": stats.usage_count,
                "success_count": stats.success_count,
                "error_count": stats.error_count,
                "success_rate": stats.success_count / max(stats.usage_count, 1) * 100,
                "last_used": stats.last_used
            }
            for tool_name, stats in self.usage_stats.items()
        }
    
    def get_tools_summary(self) -> Dict[str, Any]:
        """Get summary of all tools"""
        system_tools_count = len(self._active_tools)
        agent_tools_count = sum(len(tools) for tools in self._agent_tools.values())
        
        return {
            "total_tools": system_tools_count + agent_tools_count,
            "system_tools": system_tools_count,
            "agent_tools": agent_tools_count,
            "agents_count": len(self._agent_tools),
            "enabled_tools": len(self.get_enabled_tools()),
            "registry_summary": tool_registry.get_tools_summary()
        }
    
    def reset_stats(self):
        """Reset all usage statistics"""
        self.usage_stats.clear()
        logger.info("Tool usage statistics reset")
    
    def reload_tools(self):
        """Reload all tools (system + agent)"""
        try:
            # Clear current tools
            self._active_tools.clear()
            
            # Reload system tools
            self._initialize_system_tools()
            
            # Re-initialize tool node
            self._initialize_tool_node()
            
            logger.info("Tools reloaded successfully")
            
        except Exception as e:
            logger.error(f"Failed to reload tools: {e}")


# ================================
# GLOBAL TOOL MANAGER INSTANCE  
# ================================

# Singleton instance
tool_manager = ToolManager()

# Export
__all__ = [
    "tool_manager",
    "ToolManager"
]


# ================================
# EXAMPLE: CÁCH AGENTS ĐĂNG KÝ TOOLS
# ================================

"""
Example sử dụng trong agent:

# 1. Đăng ký tools từ AVAILABLE_TOOLS
from services.tools.tool_manager import tool_manager

# Cách 1: Đăng ký tools cơ bản
result = tool_manager.register_tools_from_available(
    agent_name="customer_service_agent",
    tool_names=["web_search", "email_template", "datetime"]
)

# Cách 2: Đăng ký với custom config
custom_configs = {
    "web_search": {
        "display_name": "Tìm kiếm thông tin khách hàng",
        "description": "Tìm kiếm thông tin liên quan đến khách hàng và sản phẩm",
        "usage_limits": {
            "calls_per_hour": 20,
            "calls_per_day": 100
        }
    },
    "email_template": {
        "display_name": "Tạo email cho khách hàng", 
        "config": {
            "template_types": ["formal", "thank_you"],
            "auto_signature": True
        }
    }
}

result = tool_manager.register_tools_from_available(
    agent_name="customer_service_agent",
    tool_names=["web_search", "email_template", "datetime"],
    custom_configs=custom_configs
)

# Kiểm tra kết quả
print(f"Đăng ký tools: {result}")
# Output: {'web_search': True, 'email_template': True, 'datetime': True}

# 3. List tools available
available_tools = tool_manager.list_available_tools_for_agent()
print(f"Tools có thể đăng ký: {list(available_tools.keys())}")

# 4. Đăng ký tool custom riêng của agent
from langchain_core.tools import tool

@tool
async def custom_crm_tool(customer_id: str) -> str:
    '''Lấy thông tin khách hàng từ CRM'''
    # Implementation
    return f"Thông tin khách hàng {customer_id}"

# Đăng ký tool custom
success = tool_manager.register_agent_tool(
    agent_name="customer_service_agent",
    tool_name="crm_lookup",
    tool_function=custom_crm_tool,
    tool_config={
        "display_name": "CRM Lookup",
        "category": "communication_tools",
        "description": "Tra cứu thông tin khách hàng trong CRM",
        "requirements": {
            "permissions": ["crm_access"],
            "min_user_level": "EMPLOYEE"
        }
    }
)

print(f"Đăng ký custom tool: {success}")

# 5. Xem tools đã đăng ký
agent_tools = tool_manager.get_agent_tools("customer_service_agent")
print(f"Tools của agent: {agent_tools}")
"""