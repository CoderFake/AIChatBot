from typing import Dict, Any, List, Optional, Type
from langchain_core.tools import BaseTool
from utils.logging import get_logger

logger = get_logger(__name__)


class ToolRegistry:
    """
    Registry for managing all available tools in the system.
    Maps tool names to their implementations and metadata.
    """
    
    def __init__(self):
        self._tools: Dict[str, Dict[str, Any]] = {}
        self._initialized = False
    
    def _register_default_tools(self):
        """Register all default tools available in the system."""
        try:
            from tools.rag_tool import rag_search_tool
            from tools.caculator_tool import calculator_tool, math_solver_tool, unit_converter_tool
            from tools.weather_tool import weather_tool, weather_forecast_tool
            from tools.web_search_tool import web_search_tool, web_scraper_tool, news_search_tool, website_summarizer_tool
            from tools.summary_tool import text_summarizer_tool, bullet_point_summarizer_tool, key_points_extractor_tool, content_analyzer_tool
            from tools.date_time_tool import datetime_tool
            
            self._register_tool("rag_search", {
                "tool_instance": rag_search_tool,
                "category": "document_tools",
                "description": "Search documents using RAG with vector similarity",
                "requires_permissions": True,
                "department_configurable": True
            })
            
            self._register_tool("calculator", {
                "tool_instance": calculator_tool,
                "category": "calculation_tools", 
                "description": "Perform mathematical calculations and operations",
                "requires_permissions": False,
                "department_configurable": False
            })
            
            self._register_tool("math_solver", {
                "tool_instance": math_solver_tool,
                "category": "calculation_tools",
                "description": "Solve mathematical word problems and equations",
                "requires_permissions": False,
                "department_configurable": False
            })
            
            self._register_tool("unit_converter", {
                "tool_instance": unit_converter_tool,
                "category": "calculation_tools",
                "description": "Convert between different units of measurement",
                "requires_permissions": False,
                "department_configurable": False
            })
        
            # Web tools
            self._register_tool("web_search", {
                "tool_instance": web_search_tool,
                "category": "web_tools",
                "description": "Search the web for current information",
                "requires_permissions": False,
                "department_configurable": True
            })
            
            self._register_tool("web_scraper", {
                "tool_instance": web_scraper_tool,
                "category": "web_tools",
                "description": "Extract text content from web pages",
                "requires_permissions": False,
                "department_configurable": True
            })
            
            self._register_tool("news_search", {
                "tool_instance": news_search_tool,
                "category": "web_tools", 
                "description": "Search for recent news articles",
                "requires_permissions": False,
                "department_configurable": True
            })
            
            self._register_tool("website_summarizer", {
                "tool_instance": website_summarizer_tool,
                "category": "web_tools",
                "description": "Summarize website content",
                "requires_permissions": False,
                "department_configurable": True
            })
            
            self._register_tool("text_summarizer", {
                "tool_instance": text_summarizer_tool,
                "category": "text_tools",
                "description": "Summarize long text content into key points",
                "requires_permissions": False,
                "department_configurable": False
            })
            
            self._register_tool("bullet_point_summarizer", {
                "tool_instance": bullet_point_summarizer_tool,
                "category": "text_tools",
                "description": "Create bullet-point summaries of text",
                "requires_permissions": False,
                "department_configurable": False
            })
            
            self._register_tool("key_points_extractor", {
                "tool_instance": key_points_extractor_tool,
                "category": "text_tools",
                "description": "Extract key points and important facts from text",
                "requires_permissions": False,
                "department_configurable": False
            })
            
            self._register_tool("content_analyzer", {
                "tool_instance": content_analyzer_tool,
                "category": "text_tools",
                "description": "Analyze text content for tone, sentiment, and themes",
                "requires_permissions": False,
                "department_configurable": False
            })
            
            self._register_tool("weather", {
                "tool_instance": weather_tool,
                "category": "information_tools",
                "description": "Get current weather information for locations",
                "requires_permissions": False,
                "department_configurable": True
            })
            
            self._register_tool("weather_forecast", {
                "tool_instance": weather_forecast_tool,
                "category": "information_tools",
                "description": "Get weather forecast for multiple days",
                "requires_permissions": False,
                "department_configurable": True
            })
            
            self._register_tool("datetime", {
                "tool_instance": datetime_tool,
                "category": "information_tools",
                "description": "Get current date and time information",
                "requires_permissions": False,
                "department_configurable": False
            })
            
            logger.info(f"Registered {len(self._tools)} default tools")
            
        except Exception as e:
            logger.error(f"Failed to register default tools: {e}")
    
    def _register_tool(self, tool_name: str, tool_config: Dict[str, Any]):
        """Register a single tool with its configuration."""
        self._tools[tool_name] = tool_config
        logger.debug(f"Registered tool: {tool_name}")
    
    def initialize(self):
        """Initialize the tool registry with all available tools."""
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
        """Get a tool instance by name."""
        if not self._initialized:
            self.initialize()
        
        tool_config = self._tools.get(tool_name)
        if tool_config:
            return tool_config.get("tool_instance")
        return None
    
    def get_all_tools(self) -> Dict[str, BaseTool]:
        """Get all registered tool instances."""
        if not self._initialized:
            self.initialize()
        
        return {
            name: config["tool_instance"] 
            for name, config in self._tools.items()
        }
    
    def get_tools_by_category(self, category: str) -> Dict[str, BaseTool]:
        """Get all tools in a specific category."""
        if not self._initialized:
            self.initialize()
        
        return {
            name: config["tool_instance"]
            for name, config in self._tools.items()
            if config.get("category") == category
        }
    
    def get_tool_categories(self) -> List[str]:
        """Get all available tool categories."""
        if not self._initialized:
            self.initialize()
        
        categories = set()
        for config in self._tools.values():
            if config.get("category"):
                categories.add(config["category"])
        
        return sorted(list(categories))
    
    def get_tool_info(self, tool_name: str) -> Optional[Dict[str, Any]]:
        """Get complete information about a tool."""
        if not self._initialized:
            self.initialize()
        
        tool_config = self._tools.get(tool_name)
        if tool_config:
            return {
                "name": tool_name,
                "description": tool_config.get("description", ""),
                "category": tool_config.get("category", "uncategorized"),
                "requires_permissions": tool_config.get("requires_permissions", False),
                "department_configurable": tool_config.get("department_configurable", False),
                "tool_schema": tool_config["tool_instance"].args if hasattr(tool_config["tool_instance"], 'args') else {}
            }
        return None
    
    def get_all_tool_info(self) -> Dict[str, Dict[str, Any]]:
        """Get information about all registered tools."""
        if not self._initialized:
            self.initialize()
        
        return {name: self.get_tool_info(name) for name in self._tools.keys()}
    
    def is_tool_available(self, tool_name: str) -> bool:
        """Check if a tool is available in the registry."""
        if not self._initialized:
            self.initialize()
        
        return tool_name in self._tools
    
    def get_tools_requiring_permissions(self) -> List[str]:
        """Get list of tools that require special permissions."""
        if not self._initialized:
            self.initialize()
        
        return [
            name for name, config in self._tools.items()
            if config.get("requires_permissions", False)
        ]
    
    def get_department_configurable_tools(self) -> List[str]:
        """Get list of tools that can be configured per department."""
        if not self._initialized:
            self.initialize()
        
        return [
            name for name, config in self._tools.items()
            if config.get("department_configurable", False)
        ]
    
    def get_registry_stats(self) -> Dict[str, Any]:
        """Get statistics about the tool registry."""
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


tool_registry = ToolRegistry()