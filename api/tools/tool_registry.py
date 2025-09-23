"""
Tool Registry Module
Central registry for all available tools in the system
"""
from typing import Dict, Optional, Any
from langchain_core.tools import BaseTool
from utils.logging import get_logger

logger = get_logger(__name__)


class ToolRegistry:
    """
    Central registry for all tools
    Manages tool registration and provides tool instances
    """
    
    def __init__(self):
        self._tools: Dict[str, Dict[str, Any]] = {}
        self._initialized = False
    
    def _register_default_tools(self):
        """
        Register all default tools
        Called during initialization
        """
        from tools.calculator_tool import CalculatorTool
        from tools.date_time_tool import DateTimeTool
        from tools.weather_tool import WeatherTool
        from tools.web_search_tool import WebSearchTool
        from tools.summary_tool import SummaryTool
        from tools.rag_tool import RAGSearchTool
        from tools.late_minutes_tool import LateMinutesTool
        
        tools_to_register = [
            CalculatorTool(),
            DateTimeTool(),
            WeatherTool(),
            WebSearchTool(),
            SummaryTool(),
            RAGSearchTool(),
            LateMinutesTool()
        ]
        
        for tool in tools_to_register:
            self.register_tool(tool)
        
        logger.info(f"Registered {len(tools_to_register)} default tools")
    
    def register_tool(self, tool_instance: BaseTool):
        """
        Register a tool instance
        Called by developers when adding new tools
        """
        tool_name = tool_instance.name
        tool_config = {
            "tool_instance": tool_instance,
            "description": tool_instance.description,
            "category": getattr(tool_instance, "category", "general"),
            "requires_permissions": getattr(tool_instance, "requires_permissions", False),
            "department_configurable": getattr(tool_instance, "department_configurable", True),
            "implementation_class": tool_instance.__class__.__name__
        }
        
        self._tools[tool_name] = tool_config
        logger.debug(f"Registered tool: {tool_name} (category: {tool_config.get('category')})")
    
    def initialize(self):
        """
        Initialize the tool registry with all available tools
        """
        if self._initialized:
            return
        
        try:
            self._register_default_tools()
            self._initialized = True
            logger.info("Tool registry initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize tool registry: {e}")
            raise
    
    def get_tool(self, tool_name: str) -> Optional[BaseTool]:
        """
        Get a tool instance by name
        """
        if not self._initialized:
            self.initialize()
        
        tool_config = self._tools.get(tool_name)
        if tool_config:
            return tool_config.get("tool_instance")
        return None
    
    def get_all_tool_info(self) -> Dict[str, Dict[str, Any]]:
        """
        Get all tool configurations for database sync
        """
        if not self._initialized:
            self.initialize()
        
        return {
            name: {
                "description": config["description"],
                "category": config["category"],
                "requires_permissions": config["requires_permissions"],
                "department_configurable": config["department_configurable"],
                "implementation_class": config["implementation_class"]
            }
            for name, config in self._tools.items()
        }
    
    def is_tool_available(self, tool_name: str) -> bool:
        """
        Check if a tool is available in the registry
        """
        if not self._initialized:
            self.initialize()
        
        return tool_name in self._tools


tool_registry = ToolRegistry()