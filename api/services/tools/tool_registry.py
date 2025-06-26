"""
Tool Registry
Quản lý định nghĩa và metadata của tools trong hệ thống
"""
from typing import Dict, Any, List, Optional
from enum import Enum

from utils.logging import get_logger

logger = get_logger(__name__)


class ToolCategory(Enum):
    """Categories của tools"""
    WEB_TOOLS = "web_tools"
    DOCUMENT_TOOLS = "document_tools"
    CALCULATION_TOOLS = "calculation_tools"
    UTILITY_TOOLS = "utility_tools"
    COMMUNICATION_TOOLS = "communication_tools"
    FILE_TOOLS = "file_tools"


class ToolRegistry:
    """
    Central registry cho tất cả tools trong hệ thống
    Chứa metadata và configuration của từng tool
    """
    
    def __init__(self):
        self._tool_definitions = self._initialize_tool_definitions()
    
    def _initialize_tool_definitions(self) -> Dict[str, Dict[str, Any]]:
        """
        Khởi tạo định nghĩa của tất cả tools
        Khi thêm tool mới, chỉ cần thêm vào đây
        """
        return {
            # WEB TOOLS
            "web_search": {
                "display_name": "Tìm kiếm Web",
                "category": ToolCategory.WEB_TOOLS.value,
                "description": "Tìm kiếm thông tin trên internet sử dụng DuckDuckGo",
                "implementation_class": "services.tools.tools.web_search_tool",
                "settings_key": "ENABLE_WEB_SEARCH_TOOL",
                "tool_config": {
                    "max_results": 5,
                    "region": "vn-vi",
                    "safesearch": "moderate",
                    "timeout_seconds": 30
                },
                "requirements": {
                    "dependencies": ["duckduckgo_search"],
                    "permissions": ["web_access"],
                    "min_user_level": "EMPLOYEE"
                },
                "usage_limits": {
                    "calls_per_hour": 100,
                    "calls_per_day": 500
                },
                "version": "1.0.0",
                "is_system": True,
                "departments_allowed": None,  # All departments
                "documentation_url": "https://docs.example.com/tools/web-search"
            },
            
            # DOCUMENT TOOLS
            "document_search": {
                "display_name": "Tìm kiếm Tài liệu",
                "category": ToolCategory.DOCUMENT_TOOLS.value,
                "description": "Tìm kiếm trong cơ sở dữ liệu vector của tài liệu",
                "implementation_class": "services.tools.tools.document_search_tool",
                "settings_key": "ENABLE_DOCUMENT_SEARCH_TOOL",
                "tool_config": {
                    "default_top_k": 5,
                    "default_threshold": 0.7,
                    "max_content_length": 10000
                },
                "requirements": {
                    "permissions": ["document_search"],
                    "min_user_level": "EMPLOYEE"
                },
                "usage_limits": {
                    "calls_per_hour": 200,
                    "calls_per_day": 1000
                },
                "version": "1.0.0",
                "is_system": True,
                "departments_allowed": None,
                "documentation_url": "https://docs.example.com/tools/document-search"
            },
            
            "document_summarize": {
                "display_name": "Tóm tắt Tài liệu",
                "category": ToolCategory.DOCUMENT_TOOLS.value,
                "description": "Tóm tắt nội dung tài liệu theo nhiều định dạng",
                "implementation_class": "services.tools.tools.document_summarize_tool",
                "settings_key": "ENABLE_DOCUMENT_SEARCH_TOOL",
                "tool_config": {
                    "summary_types": ["brief", "detailed", "bullet_points"],
                    "max_document_length": 50000
                },
                "requirements": {
                    "permissions": ["document_search", "document_read_internal"],
                    "min_user_level": "EMPLOYEE"
                },
                "usage_limits": {
                    "calls_per_hour": 50,
                    "calls_per_day": 200
                },
                "version": "1.0.0",
                "is_system": True,
                "departments_allowed": None,
                "documentation_url": "https://docs.example.com/tools/document-summarize"
            },
            
            # CALCULATION TOOLS
            "calculation": {
                "display_name": "Tính toán Toán học",
                "category": ToolCategory.CALCULATION_TOOLS.value,
                "description": "Thực hiện các phép tính toán học an toàn",
                "implementation_class": "services.tools.tools.calculation_tool",
                "settings_key": "ENABLE_CALCULATION_TOOL",
                "tool_config": {
                    "safe_mode": True,
                    "max_precision": 10,
                    "allowed_functions": ["sin", "cos", "tan", "log", "sqrt", "abs"]
                },
                "requirements": {
                    "permissions": ["calculation_access"],
                    "min_user_level": "EMPLOYEE"
                },
                "usage_limits": {
                    "calls_per_hour": 50,
                    "calls_per_day": 200
                },
                "version": "1.0.0",
                "is_system": True,
                "departments_allowed": None,
                "documentation_url": "https://docs.example.com/tools/calculation"
            },
            
            "statistics": {
                "display_name": "Tính toán Thống kê",
                "category": ToolCategory.CALCULATION_TOOLS.value,
                "description": "Thực hiện các phép tính thống kê trên dữ liệu",
                "implementation_class": "services.tools.tools.statistics_tool",
                "settings_key": "ENABLE_CALCULATION_TOOL",
                "tool_config": {
                    "max_data_points": 10000,
                    "supported_operations": ["mean", "median", "std", "var", "min", "max"]
                },
                "requirements": {
                    "permissions": ["calculation_access"],
                    "min_user_level": "EMPLOYEE"
                },
                "usage_limits": {
                    "calls_per_hour": 30,
                    "calls_per_day": 100
                },
                "version": "1.0.0",
                "is_system": True,
                "departments_allowed": None,
                "documentation_url": "https://docs.example.com/tools/statistics"
            },
            
            # UTILITY TOOLS
            "datetime": {
                "display_name": "Thông tin Thời gian",
                "category": ToolCategory.UTILITY_TOOLS.value,
                "description": "Lấy thông tin ngày giờ hiện tại",
                "implementation_class": "services.tools.tools.datetime_tool",
                "settings_key": "ENABLE_DATETIME_TOOL",
                "tool_config": {
                    "timezone": "Asia/Ho_Chi_Minh",
                    "format_locale": "vi_VN",
                    "default_format": "detailed"
                },
                "requirements": {
                    "permissions": ["datetime_access"],
                    "min_user_level": "EMPLOYEE"
                },
                "usage_limits": {
                    "calls_per_hour": 20,
                    "calls_per_day": 100
                },
                "version": "1.0.0",
                "is_system": True,
                "departments_allowed": None,
                "documentation_url": "https://docs.example.com/tools/datetime"
            },
            
            "weather": {
                "display_name": "Thông tin Thời tiết",
                "category": ToolCategory.UTILITY_TOOLS.value,
                "description": "Lấy thông tin thời tiết theo địa điểm",
                "implementation_class": "services.tools.tools.weather_tool",
                "settings_key": "ENABLE_DATETIME_TOOL",
                "tool_config": {
                    "default_location": "Ho Chi Minh City",
                    "api_provider": "placeholder",
                    "cache_duration": 1800  # 30 minutes
                },
                "requirements": {
                    "permissions": ["datetime_access"],
                    "min_user_level": "EMPLOYEE"
                },
                "usage_limits": {
                    "calls_per_hour": 20,
                    "calls_per_day": 100
                },
                "version": "1.0.0",
                "is_system": True,
                "departments_allowed": None,
                "documentation_url": "https://docs.example.com/tools/weather"
            },
            
            # FILE TOOLS
            "file_read": {
                "display_name": "Đọc File",
                "category": ToolCategory.FILE_TOOLS.value,
                "description": "Đọc nội dung file text an toàn",
                "implementation_class": "services.tools.tools.file_read_tool",
                "settings_key": "ENABLE_FILE_TOOLS",
                "tool_config": {
                    "allowed_extensions": [".txt", ".md", ".json", ".csv"],
                    "max_file_size": 10485760,  # 10MB
                    "sandbox_enabled": True
                },
                "requirements": {
                    "permissions": ["file_read"],
                    "min_user_level": "SENIOR"
                },
                "usage_limits": {
                    "calls_per_hour": 20,
                    "calls_per_day": 50
                },
                "version": "1.0.0",
                "is_system": True,
                "departments_allowed": ["IT", "ADMIN"],
                "documentation_url": "https://docs.example.com/tools/file-read"
            },
            
            "json_parse": {
                "display_name": "Parse JSON",
                "category": ToolCategory.FILE_TOOLS.value,
                "description": "Parse và format dữ liệu JSON",
                "implementation_class": "services.tools.tools.json_parse_tool",
                "settings_key": "ENABLE_FILE_TOOLS",
                "tool_config": {
                    "max_json_size": 1048576,  # 1MB
                    "pretty_print": True,
                    "validate_schema": False
                },
                "requirements": {
                    "permissions": ["calculation_access"],
                    "min_user_level": "EMPLOYEE"
                },
                "usage_limits": {
                    "calls_per_hour": 50,
                    "calls_per_day": 200
                },
                "version": "1.0.0",
                "is_system": True,
                "departments_allowed": None,
                "documentation_url": "https://docs.example.com/tools/json-parse"
            },
            
            # COMMUNICATION TOOLS
            "email_template": {
                "display_name": "Tạo Email Template",
                "category": ToolCategory.COMMUNICATION_TOOLS.value,
                "description": "Tạo template email theo các định dạng khác nhau",
                "implementation_class": "services.tools.tools.email_template_tool",
                "settings_key": "ENABLE_COMMUNICATION_TOOLS",
                "tool_config": {
                    "template_types": ["formal", "informal", "meeting", "thank_you"],
                    "localization": "vi_VN",
                    "signature_enabled": True
                },
                "requirements": {
                    "permissions": ["communication_access"],
                    "min_user_level": "EMPLOYEE"
                },
                "usage_limits": {
                    "calls_per_hour": 30,
                    "calls_per_day": 100
                },
                "version": "1.0.0",
                "is_system": True,
                "departments_allowed": None,
                "documentation_url": "https://docs.example.com/tools/email-template"
            }
        }
    
    def get_all_tools(self) -> Dict[str, Dict[str, Any]]:
        """Lấy tất cả tool definitions"""
        return self._tool_definitions.copy()
    
    def get_tool_definition(self, tool_name: str) -> Optional[Dict[str, Any]]:
        """Lấy definition của một tool cụ thể"""
        return self._tool_definitions.get(tool_name)
    
    def get_tools_by_category(self, category: str) -> Dict[str, Dict[str, Any]]:
        """Lấy tools theo category"""
        return {
            name: definition for name, definition in self._tool_definitions.items()
            if definition["category"] == category
        }
    
    def get_tool_names(self) -> List[str]:
        """Lấy danh sách tên tất cả tools"""
        return list(self._tool_definitions.keys())
    
    def get_categories(self) -> List[str]:
        """Lấy danh sách categories"""
        categories = set()
        for definition in self._tool_definitions.values():
            categories.add(definition["category"])
        return list(categories)
    
    def register_tool(
        self,
        name: str,
        display_name: str,
        category: str,
        description: str,
        implementation_class: str,
        **kwargs
    ) -> bool:
        """
        Đăng ký tool mới vào registry (dành cho agents)
        
        Args:
            name: Tên tool (unique)
            display_name: Tên hiển thị
            category: Category (phải là valid ToolCategory)
            description: Mô tả tool
            implementation_class: Path tới tool function
            **kwargs: Các config khác (tool_config, requirements, usage_limits, etc.)
            
        Returns:
            bool: True nếu đăng ký thành công
        """
        if name in self._tool_definitions:
            logger.warning(f"Tool {name} already exists in registry")
            return False
        
        # Validate category
        valid_categories = [cat.value for cat in ToolCategory]
        if category not in valid_categories:
            logger.error(f"Invalid category {category}. Valid categories: {valid_categories}")
            return False
        
        tool_definition = {
            "display_name": display_name,
            "category": category,
            "description": description,
            "implementation_class": implementation_class,
            "tool_config": kwargs.get("tool_config", {}),
            "requirements": kwargs.get("requirements", {
                "permissions": [],
                "min_user_level": "EMPLOYEE"
            }),
            "usage_limits": kwargs.get("usage_limits", {
                "calls_per_hour": 50,
                "calls_per_day": 200
            }),
            "version": kwargs.get("version", "1.0.0"),
            "is_system": kwargs.get("is_system", False),
            "departments_allowed": kwargs.get("departments_allowed"),
            "documentation_url": kwargs.get("documentation_url")
        }
        
        # Validate tool definition
        validation_errors = self.validate_tool_definition(tool_definition)
        if validation_errors:
            logger.error(f"Tool definition validation failed: {validation_errors}")
            return False
        
        self._tool_definitions[name] = tool_definition
        logger.info(f"Registered new tool: {name} in category {category}")
        return True
    
    def unregister_tool(self, name: str) -> bool:
        """
        Hủy đăng ký tool khỏi registry
        
        Args:
            name: Tên tool
            
        Returns:
            bool: True nếu hủy thành công
        """
        if name not in self._tool_definitions:
            logger.warning(f"Tool {name} not found in registry")
            return False
        
        definition = self._tool_definitions[name]
        if definition.get("is_system", False):
            logger.warning(f"Cannot unregister system tool: {name}")
            return False
        
        del self._tool_definitions[name]
        logger.info(f"Unregistered tool: {name}")
        return True
    
    def update_tool_definition(self, name: str, updates: Dict[str, Any]) -> bool:
        """
        Cập nhật definition của tool
        
        Args:
            name: Tên tool
            updates: Dict chứa các field cần update
            
        Returns:
            bool: True nếu update thành công
        """
        if name not in self._tool_definitions:
            logger.warning(f"Tool {name} not found in registry")
            return False
        
        # Không cho phép update system tools
        if self._tool_definitions[name].get("is_system", False):
            allowed_updates = ["tool_config", "usage_limits", "documentation_url"]
            filtered_updates = {k: v for k, v in updates.items() if k in allowed_updates}
            if filtered_updates != updates:
                logger.warning(f"System tool {name} can only update: {allowed_updates}")
                updates = filtered_updates
        
        self._tool_definitions[name].update(updates)
        logger.info(f"Updated tool definition: {name}")
        return True
    
    def validate_tool_definition(self, definition: Dict[str, Any]) -> List[str]:
        """
        Validate tool definition
        
        Args:
            definition: Tool definition
            
        Returns:
            List[str]: Danh sách lỗi validation
        """
        errors = []
        
        required_fields = [
            "display_name", "category", "description", 
            "implementation_class", "version"
        ]
        
        for field in required_fields:
            if field not in definition or not definition[field]:
                errors.append(f"Missing required field: {field}")
        
        # Validate category
        if "category" in definition:
            valid_categories = [cat.value for cat in ToolCategory]
            if definition["category"] not in valid_categories:
                errors.append(f"Invalid category: {definition['category']}")
        
        # Validate requirements structure
        if "requirements" in definition and definition["requirements"]:
            req = definition["requirements"]
            if not isinstance(req.get("permissions", []), list):
                errors.append("requirements.permissions must be a list")
        
        # Validate usage_limits structure
        if "usage_limits" in definition and definition["usage_limits"]:
            limits = definition["usage_limits"]
            for limit_key in ["calls_per_hour", "calls_per_day"]:
                if limit_key in limits and not isinstance(limits[limit_key], int):
                    errors.append(f"usage_limits.{limit_key} must be an integer")
        
        return errors
    
    def get_agent_tools(self, agent_name: str) -> Dict[str, Dict[str, Any]]:
        """
        Lấy tools được đăng ký bởi một agent cụ thể
        
        Args:
            agent_name: Tên agent
            
        Returns:
            Dict chứa tools của agent
        """
        agent_tools = {}
        
        for name, definition in self._tool_definitions.items():
            # Check implementation_class để xác định agent
            impl_class = definition.get("implementation_class", "")
            if f"agents.{agent_name}" in impl_class or impl_class.startswith(f"{agent_name}."):
                agent_tools[name] = definition
        
        return agent_tools
    
    def get_tools_summary(self) -> Dict[str, Any]:
        """
        Lấy tóm tắt về tools trong registry
        
        Returns:
            Dict chứa thống kê tổng quan
        """
        summary = {
            "total_tools": len(self._tool_definitions),
            "categories": {},
            "system_tools": 0,
            "agent_tools": 0
        }
        
        for name, definition in self._tool_definitions.items():
            category = definition["category"]
            if category not in summary["categories"]:
                summary["categories"][category] = 0
            summary["categories"][category] += 1
            
            if definition.get("is_system", False):
                summary["system_tools"] += 1
            else:
                summary["agent_tools"] += 1
        
        return summary
    
    def get_tool_settings_key(self, tool_name: str) -> Optional[str]:
        """
        Lấy settings key của tool để check enable/disable
        
        Args:
            tool_name: Tên tool
            
        Returns:
            Settings key hoặc None nếu không có
        """
        definition = self.get_tool_definition(tool_name)
        if definition:
            return definition.get("settings_key")
        return None
    
    def get_enabled_system_tools(self, settings_obj) -> List[str]:
        """
        Lấy danh sách system tools được enable trong settings
        
        Args:
            settings_obj: Settings object
            
        Returns:
            List tên tools được enable
        """
        enabled_tools = []
        
        for tool_name, definition in self._tool_definitions.items():
            if definition.get("is_system", False):
                settings_key = definition.get("settings_key")
                if settings_key and getattr(settings_obj, settings_key, False):
                    enabled_tools.append(tool_name)
        
        return enabled_tools


# Global registry instance
tool_registry = ToolRegistry()

# Export
__all__ = ["tool_registry", "ToolRegistry", "ToolCategory"]
