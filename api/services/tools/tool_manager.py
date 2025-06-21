from typing import Dict, List, Any, Optional, Type, Callable
from datetime import datetime
import asyncio
import importlib
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update

from models.database.tool_config import ToolConfig as DBToolConfig
from workflows.state.workflow_state import ToolConfig, UserContext, AccessLevel
from services.auth.permission_service import PermissionService
from core.exceptions import ToolNotFoundError, ToolDisabledError, PermissionDeniedError


class ToolManager:
    """
    Core tool management service
    Xử lý enable/disable tools, permission checking và dynamic loading
    """
    
    def __init__(self, db_session: AsyncSession, permission_service: PermissionService):
        self.db = db_session
        self.permission_service = permission_service
        self._tool_registry: Dict[str, Type] = {}
        self._tool_cache: Dict[str, ToolConfig] = {}
        self._loaded_tools: Dict[str, Any] = {}
        self._cache_ttl = 300  # 5 minutes
    
    async def initialize_tools(self):
        """
        Initialize tool registry với all available tools
        """
        # Register built-in tools
        await self._register_search_tools()
        await self._register_document_tools()
        await self._register_hr_tools()
        await self._register_it_tools()
        await self._register_finance_tools()
        await self._register_external_tools()
        
        # Load tool configurations from database
        await self._load_tool_configurations()
    
    async def enable_tool(
        self, 
        tool_id: str, 
        admin_user_id: str,
        configuration: Dict[str, Any] = None
    ) -> bool:
        """
        Enable một tool trong hệ thống
        """
        # Validate admin permissions
        if not await self._validate_admin_permission(admin_user_id):
            raise PermissionDeniedError("Only administrators can manage tools")
        
        # Check if tool exists in registry
        if tool_id not in self._tool_registry:
            raise ToolNotFoundError(f"Tool {tool_id} not found in registry")
        
        # Update database
        await self._update_tool_status(tool_id, True, configuration)
        
        # Clear cache
        self._clear_tool_cache(tool_id)
        
        # Log action
        await self.permission_service.create_access_audit_entry(
            user_id=admin_user_id,
            action="TOOL_ENABLED",
            resource_type="tool",
            resource_id=tool_id,
            access_granted=True,
            additional_data={"configuration": configuration}
        )
        
        return True
    
    async def disable_tool(self, tool_id: str, admin_user_id: str) -> bool:
        """
        Disable một tool trong hệ thống
        """
        # Validate admin permissions
        if not await self._validate_admin_permission(admin_user_id):
            raise PermissionDeniedError("Only administrators can manage tools")
        
        # Update database
        await self._update_tool_status(tool_id, False)
        
        # Clear cache và unload tool
        self._clear_tool_cache(tool_id)
        if tool_id in self._loaded_tools:
            del self._loaded_tools[tool_id]
        
        # Log action
        await self.permission_service.create_access_audit_entry(
            user_id=admin_user_id,
            action="TOOL_DISABLED",
            resource_type="tool",
            resource_id=tool_id,
            access_granted=True
        )
        
        return True
    
    async def get_available_tools_for_user(self, user_id: str) -> List[ToolConfig]:
        """
        Lấy danh sách tools available cho user cụ thể
        """
        user_context = await self.permission_service.get_user_context(user_id)
        if not user_context:
            return []
        
        available_tools = []
        
        # Get all enabled tools
        enabled_tools = await self._get_enabled_tools()
        
        for tool_config in enabled_tools:
            if await self._user_can_access_tool(user_context, tool_config):
                available_tools.append(tool_config)
        
        return available_tools
    
    async def load_tool_for_execution(
        self, 
        tool_id: str, 
        user_id: str,
        context: Dict[str, Any] = None
    ) -> Optional[Any]:
        """
        Load và return tool instance cho execution
        """
        # Check if tool is enabled
        tool_config = await self._get_tool_config(tool_id)
        if not tool_config or not tool_config['is_enabled']:
            raise ToolDisabledError(f"Tool {tool_id} is not enabled")
        
        # Check user permissions
        user_context = await self.permission_service.get_user_context(user_id)
        if not await self._user_can_access_tool(user_context, tool_config):
            raise PermissionDeniedError(f"User {user_id} cannot access tool {tool_id}")
        
        # Load tool if not already loaded
        if tool_id not in self._loaded_tools:
            tool_instance = await self._instantiate_tool(tool_id, tool_config)
            self._loaded_tools[tool_id] = tool_instance
        
        # Log tool usage
        await self.permission_service.create_access_audit_entry(
            user_id=user_id,
            action="TOOL_LOADED",
            resource_type="tool",
            resource_id=tool_id,
            access_granted=True,
            additional_data={"context": context}
        )
        
        return self._loaded_tools[tool_id]
    
    async def execute_tool(
        self,
        tool_id: str,
        user_id: str,
        method_name: str,
        parameters: Dict[str, Any],
        context: Dict[str, Any] = None
    ) -> Any:
        """
        Execute tool method với permission checking
        """
        # Load tool
        tool_instance = await self.load_tool_for_execution(tool_id, user_id, context)
        
        # Validate method exists
        if not hasattr(tool_instance, method_name):
            raise ToolNotFoundError(f"Method {method_name} not found in tool {tool_id}")
        
        # Execute method
        method = getattr(tool_instance, method_name)
        
        try:
            if asyncio.iscoroutinefunction(method):
                result = await method(**parameters)
            else:
                result = method(**parameters)
            
            # Log successful execution
            await self.permission_service.create_access_audit_entry(
                user_id=user_id,
                action="TOOL_EXECUTED",
                resource_type="tool",
                resource_id=f"{tool_id}.{method_name}",
                access_granted=True,
                additional_data={
                    "parameters": parameters,
                    "context": context
                }
            )
            
            return result
            
        except Exception as e:
            # Log execution error
            await self.permission_service.create_access_audit_entry(
                user_id=user_id,
                action="TOOL_EXECUTION_ERROR",
                resource_type="tool",
                resource_id=f"{tool_id}.{method_name}",
                access_granted=False,
                additional_data={
                    "error": str(e),
                    "parameters": parameters
                }
            )
            raise
    
    async def get_tool_status(self, tool_id: str) -> Dict[str, Any]:
        """
        Get current status của tool
        """
        tool_config = await self._get_tool_config(tool_id)
        if not tool_config:
            return {"status": "not_found"}
        
        return {
            "tool_id": tool_id,
            "is_enabled": tool_config['is_enabled'],
            "tool_type": tool_config['tool_type'],
            "required_permissions": tool_config['required_permissions'],
            "allowed_departments": tool_config['allowed_departments'],
            "is_loaded": tool_id in self._loaded_tools,
            "configuration": tool_config['configuration']
        }
    
    async def get_all_tools_status(self) -> Dict[str, Dict[str, Any]]:
        """
        Get status của tất cả tools
        """
        all_tools = {}
        
        # Get from registry
        for tool_id in self._tool_registry.keys():
            all_tools[tool_id] = await self.get_tool_status(tool_id)
        
        return all_tools
    
    # Private helper methods
    
    async def _register_search_tools(self):
        """Register search-related tools"""
        from app.agents.tools.search_tools import (
            BasicSearchTool,
            SemanticSearchTool,
            CrossDepartmentSearchTool
        )
        
        self._tool_registry.update({
            "basic_search": BasicSearchTool,
            "semantic_search": SemanticSearchTool,
            "cross_dept_search": CrossDepartmentSearchTool
        })
    
    async def _register_document_tools(self):
        """Register document-related tools"""
        from app.agents.tools.document_tools import (
            DocumentRetrievalTool,
            DocumentSummaryTool,
            DocumentVersionTool
        )
        
        self._tool_registry.update({
            "document_retrieval": DocumentRetrievalTool,
            "document_summary": DocumentSummaryTool,
            "document_version": DocumentVersionTool
        })
    
    async def _register_hr_tools(self):
        """Register HR-specific tools"""
        from app.agents.tools.hr_tools import (
            EmployeeSearchTool,
            PolicyLookupTool,
            BenefitsCalculatorTool
        )
        
        self._tool_registry.update({
            "employee_search": EmployeeSearchTool,
            "policy_lookup": PolicyLookupTool,
            "benefits_calculator": BenefitsCalculatorTool
        })
    
    async def _register_it_tools(self):
        """Register IT-specific tools"""
        from app.agents.tools.it_tools import (
            CodeSearchTool,
            DocumentationLookupTool,
            APISearchTool,
            TechnicalSupportTool
        )
        
        self._tool_registry.update({
            "code_search": CodeSearchTool,
            "documentation_lookup": DocumentationLookupTool,
            "api_search": APISearchTool,
            "technical_support": TechnicalSupportTool
        })
    
    async def _register_finance_tools(self):
        """Register Finance-specific tools"""
        from app.agents.tools.finance_tools import (
            FinancialReportTool,
            BudgetAnalysisTool,
            ExpenseTrackingTool,
            ComplianceCheckTool
        )
        
        self._tool_registry.update({
            "financial_reports": FinancialReportTool,
            "budget_analysis": BudgetAnalysisTool,
            "expense_tracking": ExpenseTrackingTool,
            "compliance_check": ComplianceCheckTool
        })
    
    async def _register_external_tools(self):
        """Register external API tools"""
        from app.agents.tools.external_tools import (
            WebSearchTool,
            ExternalIntegrationTool,
            EmailNotificationTool
        )
        
        self._tool_registry.update({
            "web_search": WebSearchTool,
            "external_integration": ExternalIntegrationTool,
            "email_notification": EmailNotificationTool
        })
    
    async def _load_tool_configurations(self):
        """Load tool configurations from database"""
        query = select(DBToolConfig)
        result = await self.db.execute(query)
        db_configs = result.scalars().all()
        
        for db_config in db_configs:
            tool_config = ToolConfig(
                tool_id=db_config.tool_id,
                tool_name=db_config.tool_name,
                tool_type=db_config.tool_type,
                is_enabled=db_config.is_enabled,
                required_permissions=db_config.required_permissions or [],
                allowed_departments=db_config.allowed_departments or [],
                max_access_level=AccessLevel(db_config.max_access_level),
                rate_limit=db_config.rate_limit,
                timeout_seconds=db_config.timeout_seconds,
                configuration=db_config.configuration or {}
            )
            
            self._tool_cache[db_config.tool_id] = tool_config
    
    async def _validate_admin_permission(self, user_id: str) -> bool:
        """Validate user có admin permission để manage tools"""
        user_context = await self.permission_service.get_user_context(user_id)
        if not user_context:
            return False
        
        return (
            user_context['role'] in ['ADMIN', 'SYSTEM_ADMIN'] or
            'TOOL_MANAGEMENT' in user_context['permissions']
        )
    
    async def _update_tool_status(
        self, 
        tool_id: str, 
        is_enabled: bool, 
        configuration: Dict[str, Any] = None
    ):
        """Update tool status trong database"""
        # Check if tool config exists
        query = select(DBToolConfig).where(DBToolConfig.tool_id == tool_id)
        result = await self.db.execute(query)
        existing_config = result.scalar_one_or_none()
        
        if existing_config:
            # Update existing
            update_data = {"is_enabled": is_enabled}
            if configuration:
                update_data["configuration"] = configuration
            
            update_query = update(DBToolConfig).where(
                DBToolConfig.tool_id == tool_id
            ).values(**update_data)
            
            await self.db.execute(update_query)
        else:
            # Create new
            tool_class = self._tool_registry.get(tool_id)
            if not tool_class:
                raise ToolNotFoundError(f"Tool {tool_id} not in registry")
            
            new_config = DBToolConfig(
                tool_id=tool_id,
                tool_name=getattr(tool_class, 'name', tool_id),
                tool_type=getattr(tool_class, 'tool_type', 'general'),
                is_enabled=is_enabled,
                required_permissions=getattr(tool_class, 'required_permissions', []),
                allowed_departments=getattr(tool_class, 'allowed_departments', []),
                max_access_level=getattr(tool_class, 'max_access_level', AccessLevel.PUBLIC.value),
                rate_limit=getattr(tool_class, 'rate_limit', None),
                timeout_seconds=getattr(tool_class, 'timeout_seconds', 30),
                configuration=configuration or {}
            )
            
            self.db.add(new_config)
        
        await self.db.commit()
    
    async def _get_enabled_tools(self) -> List[ToolConfig]:
        """Get all enabled tools"""
        query = select(DBToolConfig).where(DBToolConfig.is_enabled == True)
        result = await self.db.execute(query)
        db_configs = result.scalars().all()
        
        enabled_tools = []
        for db_config in db_configs:
            tool_config = ToolConfig(
                tool_id=db_config.tool_id,
                tool_name=db_config.tool_name,
                tool_type=db_config.tool_type,
                is_enabled=db_config.is_enabled,
                required_permissions=db_config.required_permissions or [],
                allowed_departments=db_config.allowed_departments or [],
                max_access_level=AccessLevel(db_config.max_access_level),
                rate_limit=db_config.rate_limit,
                timeout_seconds=db_config.timeout_seconds,
                configuration=db_config.configuration or {}
            )
            enabled_tools.append(tool_config)
        
        return enabled_tools
    
    async def _get_tool_config(self, tool_id: str) -> Optional[ToolConfig]:
        """Get tool configuration"""
        cache_key = f"tool_config:{tool_id}"
        
        # Check cache
        if cache_key in self._tool_cache:
            return self._tool_cache[cache_key]
        
        # Query database
        query = select(DBToolConfig).where(DBToolConfig.tool_id == tool_id)
        result = await self.db.execute(query)
        db_config = result.scalar_one_or_none()
        
        if not db_config:
            return None
        
        tool_config = ToolConfig(
            tool_id=db_config.tool_id,
            tool_name=db_config.tool_name,
            tool_type=db_config.tool_type,
            is_enabled=db_config.is_enabled,
            required_permissions=db_config.required_permissions or [],
            allowed_departments=db_config.allowed_departments or [],
            max_access_level=AccessLevel(db_config.max_access_level),
            rate_limit=db_config.rate_limit,
            timeout_seconds=db_config.timeout_seconds,
            configuration=db_config.configuration or {}
        )
        
        # Cache result
        self._tool_cache[cache_key] = tool_config
        
        return tool_config
    
    async def _user_can_access_tool(
        self, 
        user_context: UserContext, 
        tool_config: ToolConfig
    ) -> bool:
        """Check if user can access specific tool"""
        # Check access level
        if tool_config['max_access_level'] not in user_context['access_levels']:
            return False
        
        # Check department restrictions
        if tool_config['allowed_departments']:
            if user_context['department'] not in tool_config['allowed_departments']:
                return False
        
        # Check required permissions
        for req_perm in tool_config['required_permissions']:
            if req_perm not in user_context['permissions']:
                return False
        
        return True
    
    async def _instantiate_tool(self, tool_id: str, tool_config: ToolConfig) -> Any:
        """Instantiate tool class"""
        tool_class = self._tool_registry.get(tool_id)
        if not tool_class:
            raise ToolNotFoundError(f"Tool {tool_id} not found in registry")
        
        tool_instance = tool_class(
            config=tool_config['configuration'],
            db_session=self.db,
            permission_service=self.permission_service
        )
        
        if hasattr(tool_instance, 'initialize') and asyncio.iscoroutinefunction(tool_instance.initialize):
            await tool_instance.initialize()
        
        return tool_instance
    
    def _clear_tool_cache(self, tool_id: str):
        """Clear tool from cache"""
        cache_key = f"tool_config:{tool_id}"
        if cache_key in self._tool_cache:
            del self._tool_cache[cache_key]