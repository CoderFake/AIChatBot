"""
Tools Implementation
Chứa implementation code của các tools
Mỗi agent có thể thêm tool riêng vào đây
"""
from typing import Annotated, Dict, Any, List, Optional
from datetime import datetime
import asyncio
import json
import math
import re

# LangGraph core imports
from langchain_core.tools import tool

from config.settings import get_settings
from utils.logging import get_logger

logger = get_logger(__name__)
settings = get_settings()


# ================================
# WEB TOOLS
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


# ================================
# DOCUMENT TOOLS
# ================================

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
async def document_summarize_tool(
    document_id: str,
    summary_type: Annotated[str, "Type of summary"] = "brief"
) -> str:
    """
    Summarize a specific document.
    
    Args:
        document_id: ID of the document to summarize
        summary_type: Type of summary (brief, detailed, bullet_points)
        
    Returns:
        String containing document summary
    """
    try:
        # TODO: Implement actual document summarization
        # This is a placeholder implementation
        
        summaries = {
            "brief": f"Tóm tắt ngắn gọn của tài liệu {document_id}",
            "detailed": f"Tóm tắt chi tiết của tài liệu {document_id} với các điểm chính...",
            "bullet_points": f"• Điểm 1 từ tài liệu {document_id}\n• Điểm 2 từ tài liệu\n• Điểm 3 từ tài liệu"
        }
        
        return summaries.get(summary_type, summaries["brief"])
        
    except Exception as e:
        logger.error(f"Document summarization error: {str(e)}")
        return f"Lỗi khi tóm tắt tài liệu: {str(e)}"


# ================================
# CALCULATION TOOLS
# ================================

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
async def statistics_tool(
    data: List[float],
    operation: Annotated[str, "Statistical operation"] = "mean"
) -> str:
    """
    Perform statistical calculations on data.
    
    Args:
        data: List of numbers
        operation: Statistical operation (mean, median, mode, std, var)
        
    Returns:
        String containing statistical result
    """
    try:
        if not data:
            return "Dữ liệu rỗng"
        
        if operation == "mean":
            result = sum(data) / len(data)
            return f"Trung bình: {result:.4f}"
        elif operation == "median":
            sorted_data = sorted(data)
            n = len(sorted_data)
            if n % 2 == 0:
                result = (sorted_data[n//2-1] + sorted_data[n//2]) / 2
            else:
                result = sorted_data[n//2]
            return f"Trung vị: {result}"
        elif operation == "std":
            mean = sum(data) / len(data)
            variance = sum((x - mean) ** 2 for x in data) / len(data)
            result = math.sqrt(variance)
            return f"Độ lệch chuẩn: {result:.4f}"
        else:
            return f"Phép toán '{operation}' không được hỗ trợ"
            
    except Exception as e:
        logger.error(f"Statistics error: {str(e)}")
        return f"Lỗi khi tính toán thống kê: {str(e)}"


# ================================
# UTILITY TOOLS
# ================================

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


@tool
async def weather_tool(location: str = "Ho Chi Minh City") -> str:
    """
    Get weather information for a location.
    
    Args:
        location: Location to get weather for
        
    Returns:
        String containing weather information
    """
    try:
        # TODO: Implement actual weather API integration
        # This is a placeholder implementation
        
        return f"Thời tiết tại {location}: Nhiệt độ 28°C, có mây, độ ẩm 75%"
        
    except Exception as e:
        logger.error(f"Weather error: {str(e)}")
        return f"Lỗi khi lấy thông tin thời tiết: {str(e)}"


# ================================
# FILE TOOLS (Example for agents)
# ================================

@tool
async def file_read_tool(file_path: str) -> str:
    """
    Read content from a text file.
    
    Args:
        file_path: Path to the file to read
        
    Returns:
        String containing file content
    """
    try:
        # Security check - only allow certain file types and paths
        allowed_extensions = ['.txt', '.md', '.json', '.csv']
        if not any(file_path.lower().endswith(ext) for ext in allowed_extensions):
            return "Chỉ cho phép đọc file .txt, .md, .json, .csv"
        
        # TODO: Implement actual file reading with security checks
        # This is a placeholder implementation
        
        return f"Nội dung của file {file_path} (placeholder)"
        
    except Exception as e:
        logger.error(f"File read error: {str(e)}")
        return f"Lỗi khi đọc file: {str(e)}"


@tool
async def json_parse_tool(json_string: str) -> str:
    """
    Parse and format JSON data.
    
    Args:
        json_string: JSON string to parse
        
    Returns:
        String containing formatted JSON or error message
    """
    try:
        data = json.loads(json_string)
        formatted = json.dumps(data, indent=2, ensure_ascii=False)
        return f"JSON đã được parse:\n{formatted}"
        
    except json.JSONDecodeError as e:
        return f"Lỗi JSON format: {str(e)}"
    except Exception as e:
        logger.error(f"JSON parse error: {str(e)}")
        return f"Lỗi khi parse JSON: {str(e)}"


# ================================
# COMMUNICATION TOOLS (Example for agents)
# ================================

@tool
async def email_template_tool(
    template_type: str,
    recipient_name: str = "",
    subject: str = ""
) -> str:
    """
    Generate email templates.
    
    Args:
        template_type: Type of email template (formal, informal, meeting, thank_you)
        recipient_name: Name of the recipient
        subject: Email subject
        
    Returns:
        String containing email template
    """
    try:
        templates = {
            "formal": f"""
Kính gửi {recipient_name or '[Tên người nhận]'},

{subject or '[Nội dung chính]'}

Trân trọng,
[Tên người gửi]
            """,
            "informal": f"""
Chào {recipient_name or '[Tên]'},

{subject or '[Nội dung]'}

Cảm ơn và chúc bạn một ngày tốt lành!
[Tên]
            """,
            "meeting": f"""
Kính gửi {recipient_name or '[Tên]'},

Tôi muốn lên lịch cuộc họp để thảo luận về {subject or '[Chủ đề]'}.

Thời gian đề xuất: [Ngày/giờ]
Địa điểm: [Địa điểm/Link meeting]

Xin vui lòng xác nhận tham dự.

Trân trọng,
[Tên]
            """
        }
        
        return templates.get(template_type, "Template không tồn tại")
        
    except Exception as e:
        logger.error(f"Email template error: {str(e)}")
        return f"Lỗi khi tạo email template: {str(e)}"


# ================================
# TOOL REGISTRY - Tools available for registration
# ================================

# Dictionary chứa tất cả tools có thể đăng ký
AVAILABLE_TOOLS = {
    # Web Tools
    "web_search": web_search_tool,
    
    # Document Tools  
    "document_search": document_search_tool,
    "document_summarize": document_summarize_tool,
    
    # Calculation Tools
    "calculation": calculation_tool,
    "statistics": statistics_tool,
    
    # Utility Tools
    "datetime": datetime_tool,
    "weather": weather_tool,
    
    # File Tools
    "file_read": file_read_tool,
    "json_parse": json_parse_tool,
    
    # Communication Tools
    "email_template": email_template_tool,
}


def get_tool_function(tool_name: str):
    """
    Lấy tool function theo tên
    
    Args:
        tool_name: Tên tool
        
    Returns:
        Tool function hoặc None nếu không tìm thấy
    """
    return AVAILABLE_TOOLS.get(tool_name)


def get_available_tools() -> Dict[str, Any]:
    """
    Lấy danh sách tất cả tools có thể đăng ký
    
    Returns:
        Dict chứa tất cả available tools
    """
    return AVAILABLE_TOOLS.copy()


# Export
__all__ = [
    "AVAILABLE_TOOLS",
    "get_tool_function", 
    "get_available_tools",
    # Individual tools
    "web_search_tool",
    "document_search_tool", 
    "document_summarize_tool",
    "calculation_tool",
    "statistics_tool",
    "datetime_tool",
    "weather_tool",
    "file_read_tool",
    "json_parse_tool", 
    "email_template_tool"
]
