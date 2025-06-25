from typing import Dict, List, Any, Optional, Union, Annotated
from datetime import datetime
import asyncio
import json
import math
import re
from dataclasses import dataclass

# LangGraph core imports
from langchain_core.tools import tool
from langchain_core.messages import ToolMessage, AIMessage
from langgraph.prebuilt import ToolNode

# Local imports
from config.settings import get_settings
from utils.logging import get_logger
from core.exceptions import ToolNotFoundError, ToolDisabledError, ServiceError

logger = get_logger(__name__)
settings = get_settings()

@dataclass
class ToolUsageStats:
    """Statistics cho tool usage"""
    tool_name: str
    usage_count: int = 0
    success_count: int = 0
    error_count: int = 0
    avg_execution_time: float = 0.0
    last_used: Optional[str] = None

# ================================
# LANGGRAPH TOOLS IMPLEMENTATION
# ================================

@tool
async def web_search_tool(query: str) -> str:
    """
    Search the web for current information using DuckDuckGo.
    
    Args:
        query: The search query to look up on the web
        
    Returns:
        String containing search results
    """
    try:
        from duckduckgo_search import DDGS
        
        ddgs = DDGS()
        max_results = getattr(settings, 'WEB_SEARCH_MAX_RESULTS', 5)
        region = getattr(settings, 'WEB_SEARCH_REGION', 'vn-vi')
        safesearch = getattr(settings, 'WEB_SEARCH_SAFESEARCH', 'moderate')
        
        search_results = ddgs.text(
            keywords=query,
            max_results=max_results,
            region=region,
            safesearch=safesearch
        )
        
        results = []
        for result in search_results:
            results.append({
                "title": result.get("title", ""),
                "url": result.get("href", ""),
                "snippet": result.get("body", "")
            })
        
        if not results:
            return "Không tìm thấy kết quả tìm kiếm nào."
            
        formatted_results = []
        for i, result in enumerate(results, 1):
            formatted_results.append(
                f"{i}. **{result['title']}**\n"
                f"   URL: {result['url']}\n"
                f"   Tóm tắt: {result['snippet']}\n"
            )
        
        return "\n".join(formatted_results)
        
    except Exception as e:
        logger.error(f"Web search error: {str(e)}")
        return f"Lỗi khi tìm kiếm web: {str(e)}"

@tool
async def document_search_tool(
    query: str, 
    top_k: Annotated[int, "Number of documents to return"] = 5,
    threshold: Annotated[float, "Similarity threshold"] = 0.7
) -> str:
    """
    Search documents in the vector database.
    
    Args:
        query: The search query
        top_k: Number of top documents to return
        threshold: Minimum similarity threshold
        
    Returns:
        String containing document search results
    """
    try:
        # TODO: Implement actual vector database search
        # This is a placeholder implementation
        
        results = [
            {
                "title": f"Document {i}",
                "content": f"Relevant content for query: {query}",
                "score": 0.85,
                "metadata": {"source": f"doc_{i}.pdf"}
            }
            for i in range(1, min(top_k + 1, 4))
        ]
        
        filtered_results = [r for r in results if r["score"] >= threshold]
        
        if not filtered_results:
            return f"Không tìm thấy tài liệu phù hợp với truy vấn '{query}'"
            
        formatted_results = []
        for i, result in enumerate(filtered_results, 1):
            formatted_results.append(
                f"{i}. **{result['title']}** (Score: {result['score']:.2f})\n"
                f"   Nguồn: {result['metadata'].get('source', 'Unknown')}\n"
                f"   Nội dung: {result['content']}\n"
            )
        
        return "\n".join(formatted_results)
        
    except Exception as e:
        logger.error(f"Document search error: {str(e)}")
        return f"Lỗi khi tìm kiếm tài liệu: {str(e)}"

@tool
async def calculation_tool(expression: str) -> str:
    """
    Perform safe mathematical calculations.
    
    Args:
        expression: Mathematical expression to evaluate
        
    Returns:
        String containing calculation result
    """
    try:
        # Kiểm tra expression có an toàn không
        safe_chars = set('0123456789+-*/().e ')
        if not all(c in safe_chars for c in expression.replace(' ', '')):
            return "Biểu thức chứa ký tự không được phép"
        
        # Kiểm tra các từ khóa nguy hiểm
        dangerous_keywords = ['import', 'exec', 'eval', '__', 'open', 'file']
        if any(keyword in expression.lower() for keyword in dangerous_keywords):
            return "Biểu thức chứa từ khóa không được phép"
        
        # Thực hiện tính toán
        result = eval(expression)
        
        # Kiểm tra kết quả hợp lệ
        if isinstance(result, (int, float)):
            if math.isnan(result) or math.isinf(result):
                return "Kết quả tính toán không hợp lệ (NaN hoặc Infinity)"
            return f"Kết quả: {result}"
        else:
            return f"Kết quả: {str(result)}"
            
    except ZeroDivisionError:
        return "Lỗi: Không thể chia cho 0"
    except SyntaxError:
        return "Lỗi: Cú pháp biểu thức không đúng"
    except Exception as e:
        logger.error(f"Calculation error: {str(e)}")
        return f"Lỗi khi tính toán: {str(e)}"

@tool
async def datetime_tool(format_type: str = "current") -> str:
    """
    Get current date and time information in Vietnamese.
    
    Args:
        format_type: Type of datetime format ("current", "date", "time", "detailed")
        
    Returns:
        String containing datetime information
    """
    try:
        now = datetime.now()
        
        # Get weekday names from settings
        weekday_names = getattr(settings, 'WEEKDAY_NAMES', {
            0: "Thứ Hai", 1: "Thứ Ba", 2: "Thứ Tư", 3: "Thứ Năm",
            4: "Thứ Sáu", 5: "Thứ Bảy", 6: "Chủ Nhật"
        })
        
        weekday = weekday_names.get(now.weekday(), "Không xác định")
        
        if format_type == "current":
            return f"Hiện tại là {now.strftime('%H:%M')} ngày {now.strftime('%d/%m/%Y')} ({weekday})"
        elif format_type == "date":
            return f"Ngày {now.strftime('%d/%m/%Y')} ({weekday})"
        elif format_type == "time":
            return f"Bây giờ là {now.strftime('%H:%M:%S')}"
        elif format_type == "detailed":
            return (
                f"Thời gian chi tiết:\n"
                f"- Ngày: {now.strftime('%d/%m/%Y')}\n"
                f"- Thứ: {weekday}\n"
                f"- Giờ: {now.strftime('%H:%M:%S')}\n"
                f"- Múi giờ: UTC+7 (Việt Nam)"
            )
        else:
            return f"Định dạng không hỗ trợ. Sử dụng: current, date, time, detailed"
            
    except Exception as e:
        logger.error(f"DateTime error: {str(e)}")
        return f"Lỗi khi lấy thông tin thời gian: {str(e)}"

# ================================
# TOOL MANAGEMENT CLASS
# ================================

class ToolManager:
    """
    Manager class cho LangGraph tools với usage tracking
    """
    
    def __init__(self):
        self.usage_stats: Dict[str, ToolUsageStats] = {}
        
        # Khởi tạo available tools từ settings
        self._available_tools = {
            "web_search": web_search_tool,
            "document_search": document_search_tool, 
            "calculation": calculation_tool,
            "datetime": datetime_tool
        }
        
        # Khởi tạo tool node cho LangGraph
        self._initialize_tool_node()
    
    def _initialize_tool_node(self):
        """Initialize LangGraph ToolNode với enabled tools"""
        enabled_tools = []
        
        for tool_name, tool_func in self._available_tools.items():
            if self._is_tool_enabled(tool_name):
                enabled_tools.append(tool_func)
                
                # Initialize usage stats
                if tool_name not in self.usage_stats:
                    self.usage_stats[tool_name] = ToolUsageStats(tool_name=tool_name)
        
        self.tool_node = ToolNode(enabled_tools) if enabled_tools else None
    
    def _is_tool_enabled(self, tool_name: str) -> bool:
        """Check if tool is enabled trong settings"""
        tool_settings_map = {
            "web_search": "ENABLE_WEB_SEARCH_TOOL",
            "document_search": "ENABLE_DOCUMENT_SEARCH_TOOL",
            "calculation": "ENABLE_CALCULATION_TOOL", 
            "datetime": "ENABLE_DATETIME_TOOL"
        }
        
        setting_name = tool_settings_map.get(tool_name)
        if not setting_name:
            return False
        
        return getattr(settings, setting_name, False)
    
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
        return [
            tool_name for tool_name in self._available_tools.keys()
            if self._is_tool_enabled(tool_name)
        ]
    
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
    
    def reset_stats(self):
        """Reset all usage statistics"""
        self.usage_stats.clear()
        logger.info("Tool usage statistics reset")

# ================================
# GLOBAL TOOL MANAGER INSTANCE  
# ================================

# Singleton instance
tool_manager = ToolManager()

# Export tools for use in other modules
__all__ = [
    "tool_manager",
    "web_search_tool", 
    "document_search_tool",
    "calculation_tool",
    "datetime_tool",
    "ToolManager",
    "ToolUsageStats"
]