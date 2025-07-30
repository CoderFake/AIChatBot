from langchain_core.tools import tool
from utils.logging import get_logger
from utils.datetime_utils import CustomDateTime as datetime

logger = get_logger(__name__)


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
        
        weekday_names = {
            0: "Thứ Hai", 1: "Thứ Ba", 2: "Thứ Tư", 3: "Thứ Năm",
            4: "Thứ Sáu", 5: "Thứ Bảy", 6: "Chủ Nhật"
        }
        
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
