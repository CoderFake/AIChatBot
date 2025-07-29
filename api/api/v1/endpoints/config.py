
from fastapi import APIRouter, HTTPException, Depends, status
from typing import Dict, Any, List, Optional
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from api.v1.middleware.auth_middleware import verify_config_permission, verify_admin_permission, config_auth
from config.config_manager import config_manager
from services.llm.provider_manager import llm_provider_manager
from services.tools.tool_manager import tool_manager
from services.tools.tool_registry import tool_registry
from schemas import HealthResponse
from utils.datetime_utils import CustomDateTime as datetime
from utils.logging import get_logger

router = APIRouter()
logger = get_logger(__name__)


@router.get("/health", response_model=HealthResponse)
async def get_system_health() -> HealthResponse:
    """
    Comprehensive system health check - no auth required
    """
    try:
        llm_health = {}
        try:
            if not llm_provider_manager._initialized:
                await llm_provider_manager.initialize()
            llm_health = await llm_provider_manager.health_check_all()
        except Exception as e:
            logger.warning(f"LLM health check failed: {e}")
            llm_health = {"error": str(e)}
        
        tool_health = {}
        try:
            enabled_tools = tool_manager.get_enabled_tools()
            tool_health = {
                "status": "healthy",
                "enabled_tools": len(enabled_tools),
                "total_tools": len(tool_manager._active_tools),
                "tools": enabled_tools
            }
        except Exception as e:
            tool_health = {"status": "error", "error": str(e)}
        
        config_health = {}
        try:
            current_config = await config_manager.get_current_config()
            config_health = {
                "status": "healthy",
                "providers_count": len(current_config.get("providers", {})),
                "tools_count": len(current_config.get("tools", {})),
                "agents_count": len(current_config.get("agents", {}))
            }
        except Exception as e:
            config_health = {"status": "error", "error": str(e)}
        
        component_statuses = [
            all(llm_health.values()) if isinstance(llm_health, dict) and "error" not in llm_health else False,
            tool_health.get("status") == "healthy",
            config_health.get("status") == "healthy"
        ]
        
        overall_status = "healthy" if all(component_statuses) else "degraded"
        
        return HealthResponse(
            status=overall_status,
            components={
                "llm_providers": llm_health,
                "tools": tool_health,
                "config_manager": config_health
            },
            timestamp=datetime.now().isoformat()
        )
        
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return HealthResponse(
            status="error",
            components={"error": str(e)},
            timestamp=datetime.now().isoformat()
        )


@router.get("/")
async def get_system_configuration(
    user_context: Dict[str, Any] = Depends(verify_config_permission)
) -> Dict[str, Any]:
    """
    Get current system configuration
    Permission: config_tools, config_providers, hoặc admin
    """
    try:
        config_perms = user_context.get('config_permissions', {})
        department = user_context.get('department', '')
        
        current_config = await config_manager.get_current_config()
        
        filtered_config = {}
        
        # Admin sees everything
        if config_perms.get('can_manage_all_configs'):
            filtered_config = current_config
        else:
            # Department users see limited config
            if config_perms.get('can_manage_department_providers'):
                filtered_config['providers'] = current_config.get('providers', {})
            
            if config_perms.get('can_manage_department_tools'):
                # Filter tools by department if needed
                filtered_config['tools'] = current_config.get('tools', {})
            
            # Always show workflow and orchestrator info
            filtered_config['workflow'] = current_config.get('workflow', {})
            filtered_config['orchestrator'] = current_config.get('orchestrator', {})
        
        return {
            "config": filtered_config,
            "user_permissions": config_perms,
            "accessible_departments": config_perms.get('departments_allowed', []),
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Failed to get configuration: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Configuration retrieval failed: {str(e)}"
        )


@router.post("/tools/{tool_name}/toggle")
async def toggle_tool(
    tool_name: str,
    enabled: bool,
    user_context: Dict[str, Any] = Depends(verify_config_permission),
    db: AsyncSession = Depends(get_db)
):
    """
    Bật/tắt tool - DATABASE-FIRST
    Permission: config_tools hoặc department manager
    """
    try:
        # Check tool access permission
        has_access = await config_auth.verify_tool_config_access(tool_name, user_context)
        if not has_access:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Không có quyền config tool {tool_name}"
            )
        
        # Database-first approach
        from services.tools.tool_service import tool_service
        
        success = await tool_service.toggle_tool(db, tool_name, enabled)
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Tool {tool_name} không tồn tại trong database"
            )
        
        logger.info(f"User {user_context['user_id']} {'enabled' if enabled else 'disabled'} tool {tool_name}")
        
        return {
            "message": f"Tool {tool_name} đã được {'bật' if enabled else 'tắt'}",
            "tool_name": tool_name,
            "enabled": enabled,
            "source": "database",
            "timestamp": datetime.now().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error toggling tool {tool_name}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Lỗi khi thay đổi trạng thái tool: {str(e)}"
        )


@router.post("/providers/{provider_name}/toggle")
async def toggle_provider(
    provider_name: str,
    enabled: bool,
    user_context: Dict[str, Any] = Depends(verify_config_permission),
    db: AsyncSession = Depends(get_db)
):
    """
    Bật/tắt LLM provider
    Permission: config_providers hoặc department manager
    """
    try:
        has_access = await config_auth.verify_provider_config_access(provider_name, user_context)
        if not has_access:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Không có quyền config provider {provider_name}"
            )
        
        # Apply config change via config manager
        change_data = {
            "change_type": "provider_enabled" if enabled else "provider_disabled",
            "component_name": provider_name,
            "config": enabled
        }
        
        result = await config_manager.apply_config_change(change_data)
        
        if not result.get("success"):
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=result.get("error", "Failed to apply config change")
            )
        
        logger.info(f"User {user_context['user_id']} {'enabled' if enabled else 'disabled'} provider {provider_name}")
        
        return {
            "message": f"Provider {provider_name} đã được {'bật' if enabled else 'tắt'}",
            "provider_name": provider_name,
            "enabled": enabled,
            "change_id": result.get("change_id"),
            "timestamp": datetime.now().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error toggling provider {provider_name}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Lỗi khi thay đổi trạng thái provider: {str(e)}"
        )


@router.get("/tools")
async def list_available_tools(
    user_context: Dict[str, Any] = Depends(verify_config_permission),
    db: AsyncSession = Depends(get_db)
):
    """
    Lấy danh sách tools user có thể config - DATABASE-FIRST
    """
    try:
        from services.tools.tool_service import tool_service
        
        config_perms = user_context.get('config_permissions', {})
        department = user_context.get('department', '')
        
        all_tools = await tool_service.get_all_tools(db)
        accessible_tools = {}
        
        for tool in all_tools:
            can_access = False
            if config_perms.get('can_manage_all_tools'):
                can_access = True
            elif config_perms.get('can_manage_department_tools'):
                if tool.is_available_for_department(department):
                    can_access = True
            
            if can_access:
                accessible_tools[tool.name] = {
                    "name": tool.name,
                    "display_name": tool.display_name,
                    "description": tool.description,
                    "category": tool.category,
                    "currently_enabled": tool.is_enabled,
                    "can_toggle": True,
                    "version": tool.version,
                    "is_system": tool.is_system,
                    "requirements": tool.requirements or {},
                    "usage_limits": tool.usage_limits or {},
                    "tool_config": tool.tool_config or {},
                    "departments_allowed": tool.departments_allowed,
                    "source": "database"
                }
        
        enabled_count = sum(1 for tool in accessible_tools.values() if tool.get("currently_enabled", False))
        
        return {
            "tools": accessible_tools,
            "summary": {
                "total_available": len(accessible_tools),
                "enabled": enabled_count,
                "disabled": len(accessible_tools) - enabled_count,
                "categories": list(set([tool.get("category", "utility_tools") for tool in accessible_tools.values()])),
                "source": "database"
            },
            "user_permissions": config_perms,
            "department": department
        }
        
    except Exception as e:
        logger.error(f"Error listing tools from database: {e}")
        
        # Fallback to registry if database fails
        logger.warning("Database failed, using registry fallback")
        try:
            from config.settings import get_settings
            
            config_perms = user_context.get('config_permissions', {})
            department = user_context.get('department', '')
            settings = get_settings()
            
            all_tools = tool_registry.get_all_tools()
            accessible_tools = {}
            
            for tool_name, tool_def in all_tools.items():
                can_access = False
                if config_perms.get('can_manage_all_tools'):
                    can_access = True
                elif config_perms.get('can_manage_department_tools'):
                    departments_allowed = tool_def.get('departments_allowed')
                    if not departments_allowed or department in departments_allowed:
                        can_access = True
                
                if can_access:
                    is_enabled = settings.is_tool_enabled(tool_name)
                    accessible_tools[tool_name] = {
                        "name": tool_name,
                        "display_name": tool_def.get("display_name", tool_name),
                        "description": tool_def.get("description", ""),
                        "category": tool_def.get("category", "utility_tools"),
                        "currently_enabled": is_enabled,
                        "can_toggle": False,  # Không toggle được trong fallback mode
                        "version": tool_def.get("version", "1.0.0"),
                        "source": "registry_fallback",
                        "warning": "Database unavailable"
                    }
            
            enabled_count = sum(1 for tool in accessible_tools.values() if tool.get("currently_enabled", False))
            
            return {
                "tools": accessible_tools,
                "summary": {
                    "total_available": len(accessible_tools),
                    "enabled": enabled_count,
                    "disabled": len(accessible_tools) - enabled_count,
                    "source": "registry_fallback"
                },
                "warning": "Database unavailable, using registry fallback",
                "user_permissions": config_perms,
                "department": department
            }
            
        except Exception as fallback_error:
            logger.error(f"Both database and registry failed: {fallback_error}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Both database and fallback failed: {str(fallback_error)}"
            )


@router.get("/providers")
async def list_available_providers(
    user_context: Dict[str, Any] = Depends(verify_config_permission)
):
    """
    Lấy danh sách providers user có thể config
    """
    try:
        config_perms = user_context.get('config_permissions', {})
        
        current_config = await config_manager.get_current_config()
        providers = current_config.get('providers', {})
        
        accessible_providers = {}
        
        if config_perms.get('can_manage_all_providers'):
            accessible_providers = providers
        elif config_perms.get('can_manage_department_providers'):
            accessible_providers = providers
        
        return {
            "providers": accessible_providers,
            "total": len(accessible_providers),
            "user_permissions": config_perms
        }
        
    except Exception as e:
        logger.error(f"Error listing providers: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Lỗi khi lấy danh sách providers: {str(e)}"
        )


@router.post("/reload")
async def reload_system_configuration(
    user_context: Dict[str, Any] = Depends(verify_admin_permission)
):
    """
    Reload toàn bộ system configuration
    Chỉ admin mới có quyền reload
    """
    try:
        logger.info(f"System reload initiated by user {user_context['user_id']}")
        
        await config_manager.initialize()
        
        if llm_provider_manager._initialized:
            llm_provider_manager._initialized = False
            await llm_provider_manager.initialize()
        
        tool_manager.reload_tools()
        
        updated_config = await config_manager.get_current_config()
        
        logger.info("System configuration reloaded successfully")
        
        return {
            "message": "System configuration reloaded successfully",
            "timestamp": datetime.now().isoformat(),
            "reloaded_by": user_context['user_id'],
            "summary": {
                "providers": len(updated_config.get("providers", {})),
                "tools": len(updated_config.get("tools", {})),
                "agents": len(updated_config.get("agents", {}))
            }
        }
        
    except Exception as e:
        logger.error(f"System reload failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"System reload failed: {str(e)}"
        )
