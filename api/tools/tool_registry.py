"""
Tool Registry with implemented tools
"""
from typing import Dict, Any, List, Optional
from langchain_core.tools import BaseTool

from api.tools.calculator_tool import CalculatorTool
from api.tools.date_time_tool import DateTimeTool  
from api.tools.weather_tool import WeatherTool
from api.tools.web_search_tool import WebSearchTool
from api.tools.summary_tool import SummaryTool
from api.tools.rag_tool import RAGSearchTool

from utils.logging import get_logger

logger = get_logger(__name__)


class ToolRegistry:
    """
    Central registry for all available tools
    Manages tool registration, configuration, and metadata
    """
    
    def __init__(self):
        self._tools: Dict[str, Dict[str, Any]] = {}
        self._initialized = False
    
    def _register_default_tools(self):
        """Register all available tools with their configurations"""
        try:
            logger.info("Registering default tools...")
            
            # Calculator Tool
            self._register_tool("calculator", {
                "tool_instance": CalculatorTool(),
                "category": "utility_tools",
                "description": "Performs mathematical calculations including basic arithmetic, trigonometry, and advanced math functions",
                "requires_permissions": False,
                "department_configurable": False,
                "implementation_class": "api.tools.calculator_tool.CalculatorTool"
            })
            
            # DateTime Tool
            self._register_tool("datetime", {
                "tool_instance": DateTimeTool(),
                "category": "utility_tools", 
                "description": "Handles date and time operations including formatting, timezone conversion, and date arithmetic",
                "requires_permissions": False,
                "department_configurable": True,
                "implementation_class": "api.tools.date_time_tool.DateTimeTool"
            })
            
            # Weather Tool
            self._register_tool("weather", {
                "tool_instance": WeatherTool(),
                "category": "information_tools",
                "description": "Provides current weather conditions and forecasts for any location worldwide",
                "requires_permissions": False,
                "department_configurable": True,
                "implementation_class": "api.tools.weather_tool.WeatherTool"
            })
            
            # Web Search Tool
            self._register_tool("web_search", {
                "tool_instance": WebSearchTool(),
                "category": "information_tools",
                "description": "Searches the web using multiple search engines (DuckDuckGo, Google, Bing) for current information",
                "requires_permissions": False,
                "department_configurable": True,
                "implementation_class": "api.tools.web_search_tool.WebSearchTool"
            })
            
            # Summary Tool
            self._register_tool("summary", {
                "tool_instance": SummaryTool(),
                "category": "text_processing_tools",
                "description": "Summarizes text content in various formats including concise, bullet points, and detailed summaries",
                "requires_permissions": False,
                "department_configurable": True,
                "implementation_class": "api.tools.summary_tool.SummaryTool"
            })
            
            # RAG Search Tool
            self._register_tool("rag_search", {
                "tool_instance": RAGSearchTool(),
                "category": "information_tools", 
                "description": "Searches through documents using semantic similarity based on user's department and access levels",
                "requires_permissions": True,
                "department_configurable": True,
                "implementation_class": "api.tools.rag_tool.RAGSearchTool"
            })
            
            logger.info(f"Successfully registered {len(self._tools)} tools")
            
        except Exception as e:
            logger.error(f"Failed to register default tools: {e}")
            raise
    
    def _register_tool(self, tool_name: str, tool_config: Dict[str, Any]):
        """Register a single tool with its configuration"""
        self._tools[tool_name] = tool_config
        logger.debug(f"Registered tool: {tool_name} (category: {tool_config.get('category')})")
    
    def initialize(self):
        """Initialize the tool registry with all available tools"""
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
        """Get a tool instance by name"""
        if not self._initialized:
            self.initialize()
        
        tool_config = self._tools.get(tool_name)
        if tool_config:
            return tool_config.get("tool_instance")
        return None
    
    def get_all_tools(self) -> Dict[str, BaseTool]:
        """Get all registered tool instances"""
        if not self._initialized:
            self.initialize()
        
        return {
            name: config["tool_instance"] 
            for name, config in self._tools.items()
        }
    
    def get_all_tool_info(self) -> Dict[str, Dict[str, Any]]:
        """Get all tool configurations (for database sync)"""
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
    
    def get_tools_by_category(self, category: str) -> Dict[str, BaseTool]:
        """Get all tools in a specific category"""
        if not self._initialized:
            self.initialize()
        
        return {
            name: config["tool_instance"]
            for name, config in self._tools.items()
            if config.get("category") == category
        }
    
    def get_tool_categories(self) -> List[str]:
        """Get all available tool categories"""
        if not self._initialized:
            self.initialize()
        
        categories = set()
        for config in self._tools.values():
            categories.add(config.get("category", "uncategorized"))
        
        return sorted(list(categories))
    
    def is_tool_available(self, tool_name: str) -> bool:
        """Check if a tool is available in the registry"""
        if not self._initialized:
            self.initialize()
        
        return tool_name in self._tools
    
    def get_tools_requiring_permissions(self) -> List[str]:
        """Get list of tools that require special permissions"""
        if not self._initialized:
            self.initialize()
        
        return [
            name for name, config in self._tools.items()
            if config.get("requires_permissions", False)
        ]
    
    def get_department_configurable_tools(self) -> List[str]:
        """Get list of tools that can be configured per department"""
        if not self._initialized:
            self.initialize()
        
        return [
            name for name, config in self._tools.items()
            if config.get("department_configurable", False)
        ]
    
    def get_registry_stats(self) -> Dict[str, Any]:
        """Get statistics about the tool registry"""
        if not self._initialized:
            self.initialize()
        
        category_counts = {}
        for config in self._tools.values():
            category = config.get("category", "uncategorized")
            category_counts[category] = category_counts.get(category, 0) + 1
        
        return {
            "total_tools": len(self._tools),
            "categories": len(self.get_tool_categories()),
            "category_breakdown": category_counts,
            "tools_requiring_permissions": len(self.get_tools_requiring_permissions()),
            "department_configurable_tools": len(self.get_department_configurable_tools()),
            "initialized": self._initialized
        }


# Global instance
tool_registry = ToolRegistry()