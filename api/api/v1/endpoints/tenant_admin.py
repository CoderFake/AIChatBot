"""Tenant admin endpoints for managing tenant-specific operations"""
from typing import Any, Dict, Optional, List
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel, Field

from config.database import get_db
from api.v1.middleware.middleware import RequireAtLeastAdmin
from models.database.agent import WorkflowAgent
from models.schemas.responses.tenant import OperationResult
from common.timezones import TimezoneGroups
from services.tenant.tenant_service import get_tenant_service
from services.tenant.settings_service import SettingsService
from services.auth.validate_permission import ValidatePermission
from models.schemas.responses.tenant import TenantSettingsResponse
from models.schemas.request.tenant import TenantSettingsRequest
from utils.logging import get_logger

logger = get_logger(__name__)
router = APIRouter()


async def _invalidate_tenant_cache(db: AsyncSession, cache_invalidation_info: Dict[str, Any]) -> None:
    """
    Helper method to invalidate tenant cache after successful operations
    """
    try:
        tenant_service = await get_tenant_service(db)
        await tenant_service.invalidate_tenant_caches(
            cache_invalidation_info["tenant_id"],
            cache_invalidation_info["entity_types"]
        )
        logger.info(f"Cache invalidated for tenant {cache_invalidation_info['tenant_id']}, entities: {cache_invalidation_info['entity_types']}")
    except Exception as e:
        logger.warning(f"Cache invalidation failed: {e}")


# ==================== WORKFLOW AGENT CONFIGURATION ====================

class WorkflowAgentConfigRequest(BaseModel):
    provider_name: str
    model_name: str
    model_configuration: Optional[Dict[str, Any]] = Field(default=None, alias="model_config")
    max_iterations: Optional[int] = 10
    timeout_seconds: Optional[int] = 300
    confidence_threshold: Optional[float] = 0.7

    class Config:
        allow_population_by_field_name = True


class WorkflowAgentResponse(BaseModel):
    id: str
    tenant_id: str
    provider_name: str
    model_name: str
    model_configuration: Dict[str, Any] = Field(alias="model_config")
    api_keys: List[str]
    max_iterations: int
    timeout_seconds: int
    confidence_threshold: float
    is_active: bool

    class Config:
        allow_population_by_field_name = True
        by_alias = True


@router.get("/workflow-agent", response_model=WorkflowAgentResponse, summary="Get workflow agent config")
async def get_workflow_agent_config(
    db: AsyncSession = Depends(get_db),
    user_ctx: dict = Depends(RequireAtLeastAdmin())
) -> WorkflowAgentResponse:
    """Get workflow agent configuration for tenant"""
    try:
        from services.agents.workflow_agent_service import WorkflowAgentService

        tenant_id = user_ctx.get("tenant_id")

        workflow_service = WorkflowAgentService(db)
        workflow_agent = await workflow_service.get_or_create_workflow_agent(tenant_id)
        workflow_agent_config = await workflow_service.get_workflow_agent_config(tenant_id)

        return WorkflowAgentResponse(
            id=workflow_agent["id"],
            tenant_id=workflow_agent["tenant_id"],
            provider_name=workflow_agent_config["provider_name"],
            model_name=workflow_agent_config["model_name"],
            model_config=workflow_agent_config["model_config"],
            api_keys=workflow_agent_config["api_keys"],
            max_iterations=workflow_agent_config["max_iterations"],
            timeout_seconds=workflow_agent_config["timeout_seconds"],
            confidence_threshold=workflow_agent_config["confidence_threshold"],
            is_active=workflow_agent_config["is_active"]
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get workflow agent: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get workflow agent: {str(e)}"
        )


@router.post("/workflow-agent", response_model=WorkflowAgentResponse, summary="Create or update workflow agent")
async def create_or_update_workflow_agent(
    request: WorkflowAgentConfigRequest,
    db: AsyncSession = Depends(get_db),
    user_ctx: dict = Depends(RequireAtLeastAdmin())
) -> WorkflowAgentResponse:
    """Create or update workflow agent for tenant (only one per tenant)"""
    try:
        tenant_id = user_ctx.get("tenant_id")

        result = await db.execute(
            select(WorkflowAgent).where(WorkflowAgent.tenant_id == tenant_id)
        )
        existing_agent = result.scalar_one_or_none()

        if existing_agent:
            # Update existing
            existing_agent.provider_name = request.provider_name
            existing_agent.model_name = request.model_name
            existing_agent.model_config = request.model_config
            existing_agent.max_iterations = request.max_iterations or 10
            existing_agent.timeout_seconds = request.timeout_seconds or 300
            existing_agent.confidence_threshold = request.confidence_threshold or 0.7
            await db.commit()
            workflow_agent = existing_agent
        else:
            workflow_agent = WorkflowAgent(
                tenant_id=tenant_id,
                provider_name=request.provider_name,
                model_name=request.model_name,
                model_config=request.model_config,
                max_iterations=request.max_iterations or 10,
                timeout_seconds=request.timeout_seconds or 300,
                confidence_threshold=request.confidence_threshold or 0.7,
                is_active=True
            )
            db.add(workflow_agent)
            await db.commit()
            await db.refresh(workflow_agent)

        await _invalidate_tenant_cache(db, {
            "tenant_id": tenant_id,
            "entity_types": ['workflow_agents', 'provider_configs', 'provider_api_keys']
        })

        # Invalidate settings cache
        settings_service = SettingsService(db)
        await settings_service._invalidate_settings_cache(tenant_id)

        return WorkflowAgentResponse(
            id=str(workflow_agent.id),
            tenant_id=str(workflow_agent.tenant_id),
            provider_name=workflow_agent.provider_name,
            model_name=workflow_agent.model_name,
            model_config=workflow_agent.model_config or {},
            max_iterations=workflow_agent.max_iterations,
            timeout_seconds=workflow_agent.timeout_seconds,
            confidence_threshold=workflow_agent.confidence_threshold,
            is_active=workflow_agent.is_active
        )

    except Exception as e:
        logger.error(f"Failed to create/update workflow agent: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create/update workflow agent: {str(e)}"
        )


# ==================== TENANT SETTINGS CONFIGURATION ====================

@router.get("/settings", response_model=TenantSettingsResponse, summary="Get tenant settings")
async def get_tenant_settings(
    db: AsyncSession = Depends(get_db),
    user_ctx: dict = Depends(RequireAtLeastAdmin())
) -> TenantSettingsResponse:
    """Get tenant settings including branding"""
    try:
        tenant_id = user_ctx.get("tenant_id")
        settings_service = SettingsService(db)

        settings_data = await settings_service.get_tenant_settings_with_mapping(tenant_id)

        response_data = dict(settings_data)
        response_data['chatbot_name'] = settings_data.get('chatbot_name')
        response_data['logo_url'] = settings_data.get('logo_url')
        response_data['bot_name'] = settings_data.get('chatbot_name')  
        response_data['branding'] = {
            'logo_url': settings_data.get('logo_url')
        }

        return TenantSettingsResponse(**response_data)

    except Exception as e:
        logger.error(f"Failed to get tenant settings: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get tenant settings: {str(e)}"
        )


@router.put("/settings", response_model=TenantSettingsResponse, summary="Update tenant settings")
async def update_tenant_settings(
    request: TenantSettingsRequest,
    db: AsyncSession = Depends(get_db),
    user_ctx: dict = Depends(RequireAtLeastAdmin())
) -> TenantSettingsResponse:
    """Update tenant settings including branding"""
    try:
        tenant_id = user_ctx.get("tenant_id")
        settings_service = SettingsService(db)

        updated_settings = await settings_service.update_tenant_basic_settings(
            tenant_id=tenant_id,
            tenant_name=request.tenant_name,
            description=request.description,
            timezone=request.timezone,
            locale=request.locale
        )

        bot_name_to_update = request.bot_name or request.chatbot_name
        if bot_name_to_update is not None:
            await settings_service.update_bot_name(tenant_id, bot_name_to_update)
            updated_settings = await settings_service.get_tenant_settings_with_mapping(tenant_id)

        logo_url_to_update = None
        if request.branding and request.branding.get("logo_url") is not None:
            logo_url_to_update = request.branding["logo_url"]
        elif request.logo_url is not None:
            logo_url_to_update = request.logo_url

        if logo_url_to_update is not None:
            await settings_service.update_logo_url(tenant_id, logo_url_to_update)
            updated_settings = await settings_service.get_tenant_settings_with_mapping(tenant_id)

        response_data = dict(updated_settings)
        response_data['chatbot_name'] = updated_settings.get('chatbot_name')
        response_data['logo_url'] = updated_settings.get('logo_url')
        response_data['bot_name'] = updated_settings.get('chatbot_name') 
        response_data['branding'] = {
            'logo_url': updated_settings.get('logo_url')
        }

        return TenantSettingsResponse(**response_data)

    except Exception as e:
        logger.error(f"Failed to update tenant settings: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update tenant settings: {str(e)}"
        )


# ==================== DYNAMIC DATA ENDPOINTS ====================

class ModelResponse(BaseModel):
    id: str
    name: str

class ProviderResponse(BaseModel):
    id: str
    name: str
    models: List[ModelResponse]


class DynamicDataResponse(BaseModel):
    providers: List[ProviderResponse]
    tools: List[Dict[str, Any]]
    timezones: List[Dict[str, str]]
    locales: List[Dict[str, str]]


class ProviderApiKeysRequest(BaseModel):
    api_keys: List[str]


class ProviderApiKeysResponse(BaseModel):
    provider_name: str
    api_keys: List[str]
    total_keys: int


@router.get("/dynamic-data", response_model=DynamicDataResponse, summary="Get dynamic data for settings")
async def get_dynamic_data(
    db: AsyncSession = Depends(get_db),
    user_ctx: dict = Depends(RequireAtLeastAdmin())
) -> DynamicDataResponse:
    """Get available providers, models, timezones, and locales for tenant"""
    try:
        tenant_id = user_ctx.get("tenant_id")

        validator = ValidatePermission(db)
        providers_result = await validator.get_providers_by_role_context(
            user_role=user_ctx.get("role"),
            tenant_id=tenant_id,
            department_id=user_ctx.get("department_id")
        )

        providers = []
        if "providers" in providers_result:
            for provider_data in providers_result["providers"]:
                models_data = provider_data.get("models", [])
                
                model_responses = []
                for model in models_data:
                    if isinstance(model, dict) and "id" in model and "model_name" in model:
                        model_responses.append(ModelResponse(
                            id=str(model["id"]),
                            name=model["model_name"]
                        ))
                    elif isinstance(model, str):
                        model_responses.append(ModelResponse(
                            id=model, 
                            name=model
                        ))
                
                if not model_responses:
                    model_responses.append(ModelResponse(
                        id=f"{provider_data['provider_name']}-default",
                        name=f"{provider_data['provider_name']}-default"
                    ))

                providers.append(ProviderResponse(
                    id=str(provider_data.get("id", provider_data["provider_name"])),
                    name=provider_data["provider_name"],
                    models=model_responses
                ))

        timezone_data = TimezoneGroups.get_timezone_groups()
        timezones = []

        for region_name, tz_list in timezone_data.items():
            for tz in tz_list:
                timezones.append({
                    "code": tz["value"],
                    "name": f"{tz['label']} ({region_name})"
                })

        locales = [
            {"code": "en_US", "name": "English (US)"},
            {"code": "vi_VN", "name": "Tiếng Việt"},
            {"code": "ja_JP", "name": "日本語"},
            {"code": "ko_KR", "name": "한국어"},
            {"code": "zh_CN", "name": "中文 (简体)"},
            {"code": "zh_TW", "name": "中文 (繁體)"},
        ]

        from services.tools.tool_service import ToolService
        tool_service = ToolService(db)
        tools_data = await tool_service.get_tools_for_tenant_admin(tenant_id)

        return DynamicDataResponse(
            providers=providers,
            tools=tools_data,
            timezones=timezones,
            locales=locales
        )

    except Exception as e:
        logger.error(f"Failed to get dynamic data: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get dynamic data: {str(e)}"
        )


# ==================== PROVIDER API KEYS MANAGEMENT ====================

@router.get("/providers/{provider_name}/api-keys", response_model=ProviderApiKeysResponse, summary="Get API keys for a provider")
async def get_provider_api_keys(
    provider_name: str,
    db: AsyncSession = Depends(get_db),
    user_ctx: dict = Depends(RequireAtLeastAdmin())
) -> ProviderApiKeysResponse:
    """Get API keys for a specific provider (admin only)"""
    try:
        tenant_id = user_ctx.get("tenant_id")

        from services.providers.provider_api_keys_service import ProviderApiKeysService
        api_keys_service = ProviderApiKeysService(db)

        result = await api_keys_service.get_provider_api_keys(tenant_id, provider_name)

        return ProviderApiKeysResponse(**result)

    except Exception as e:
        logger.error(f"Failed to get API keys for provider {provider_name}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get API keys for provider {provider_name}: {str(e)}"
        )


@router.put("/providers/{provider_name}/api-keys", response_model=ProviderApiKeysResponse, summary="Update API keys for a provider")
async def update_provider_api_keys(
    provider_name: str,
    request: ProviderApiKeysRequest,
    db: AsyncSession = Depends(get_db),
    user_ctx: dict = Depends(RequireAtLeastAdmin())
) -> ProviderApiKeysResponse:
    """Update API keys for a specific provider (admin only)"""
    try:
        tenant_id = user_ctx.get("tenant_id")

        from services.providers.provider_api_keys_service import ProviderApiKeysService
        api_keys_service = ProviderApiKeysService(db)

        result = await api_keys_service.update_provider_api_keys(
            tenant_id=tenant_id,
            provider_name=provider_name,
            api_keys=request.api_keys
        )

        await _invalidate_tenant_cache(db, {
            "tenant_id": tenant_id,
            "entity_types": ['provider_configs', 'provider_api_keys']
        })

        settings_service = SettingsService(db)
        await settings_service._invalidate_settings_cache(tenant_id)

        return ProviderApiKeysResponse(**result)

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update API keys for provider {provider_name}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update API keys for provider {provider_name}: {str(e)}"
        )


# ==================== DEPARTMENT CRUD ====================

class CreateDepartmentRequest(BaseModel):
    department_name: str
    description: Optional[str] = None

    # Agent configuration
    agent_name: str
    agent_description: str

    # Provider configuration
    provider_id: str
    model_id: Optional[str] = None
    provider_config: Optional[Dict[str, Any]] = None

    # Tool assignments
    tool_ids: Optional[List[str]] = None


class DepartmentResponse(BaseModel):
    id: str
    department_name: str
    description: Optional[str]
    is_active: bool
    agent_count: int = 0
    user_count: int = 0
    created_at: Optional[str] = None
    tenant_name: Optional[str] = None

    # Agent details
    agent: Optional[Dict[str, Any]] = None
    # Tool assignments
    tool_assignments: Optional[List[Dict[str, Any]]] = None


@router.get("/departments", response_model=List[DepartmentResponse], summary="List departments")
async def list_departments(
    db: AsyncSession = Depends(get_db),
    user_ctx: dict = Depends(RequireAtLeastAdmin())
) -> List[DepartmentResponse]:
    """List all departments for the tenant"""
    try:
        tenant_id = user_ctx.get("tenant_id")

        from services.department.department_service import DepartmentService
        dept_service = DepartmentService(db)

        departments_data = await dept_service.get_departments_by_tenant(tenant_id)

        response = []
        for dept in departments_data:
            response.append(DepartmentResponse(
                id=dept["id"],
                department_name=dept["department_name"],
                description=dept["description"],
                is_active=dept["is_active"],
                agent_count=dept["agent_count"],
                user_count=dept["user_count"],
                created_at=dept["created_at"],
                tenant_name=dept["tenant_name"],
                agent=dept.get("agent"),
                tool_assignments=dept.get("tool_assignments", [])
            ))

        return response

    except Exception as e:
        logger.error(f"Failed to list departments: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list departments: {str(e)}"
        )


@router.post("/departments", response_model=DepartmentResponse, summary="Create department with agent, provider and tools")
async def create_department(
    request: CreateDepartmentRequest,
    db: AsyncSession = Depends(get_db),
    user_ctx: dict = Depends(RequireAtLeastAdmin())
) -> DepartmentResponse:
    """Create new department with agent, provider configuration and tool assignments"""
    try:
        tenant_id = user_ctx.get("tenant_id")

        from services.department.department_service import DepartmentService
        dept_service = DepartmentService(db)

        result = await dept_service.create_department(
            tenant_id=tenant_id,
            department_name=request.department_name,
            agent_name=request.agent_name,
            agent_description=request.agent_description,
            provider_id=request.provider_id,
            model_id=request.model_id,
            config_data=request.provider_config,
            department_description=request.description,
            tool_ids=request.tool_ids
        )

        if "cache_invalidation" in result:
            await _invalidate_tenant_cache(db, result["cache_invalidation"])

        return DepartmentResponse(
            id=result["department"]["id"],
            department_name=result["department"]["department_name"],
            description=result["department"]["description"],
            is_active=result["department"]["is_active"],
            agent_count=result["department"]["agent_count"],
            user_count=0,
            created_at=result["department"]["created_at"],
            tenant_name=result["department"]["tenant_name"],
            agent=result["agent"],
            tool_assignments=result["tool_assignments"]
        )

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Failed to create department: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create department: {str(e)}"
        )


@router.get("/departments/{department_id}", response_model=DepartmentResponse, summary="Get department")
async def get_department(
    department_id: str,
    db: AsyncSession = Depends(get_db),
    user_ctx: dict = Depends(RequireAtLeastAdmin())
) -> DepartmentResponse:
    """Get department details"""
    try:
        from services.department.department_service import DepartmentService
        dept_service = DepartmentService(db)

        department_data = await dept_service.get_department(department_id)

        if not department_data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Department not found"
            )

        return DepartmentResponse(
            id=department_data["id"],
            department_name=department_data["name"], 
            description=department_data["description"],
            is_active=department_data["is_active"],
            agent_count=department_data["agent_count"],
            user_count=0
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get department: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get department: {str(e)}"
        )


@router.put("/departments/{department_id}", response_model=DepartmentResponse, summary="Update department with agent and tools")
async def update_department(
    department_id: str,
    request: CreateDepartmentRequest,
    db: AsyncSession = Depends(get_db),
    user_ctx: dict = Depends(RequireAtLeastAdmin())
) -> DepartmentResponse:
    """Update department with agent, provider, and tool assignments"""
    try:
        tenant_id = user_ctx.get("tenant_id")

        from services.department.department_service import DepartmentService
        dept_service = DepartmentService(db)
        result = await dept_service.update_department(
            department_id=department_id,
            tenant_id=tenant_id,
            department_name=request.department_name,
            agent_name=request.agent_name,
            agent_description=request.agent_description,
            provider_id=request.provider_id,
            model_id=request.model_id,
            config_data=request.provider_config,
            department_description=request.description,
            tool_ids=request.tool_ids,
            role = user_ctx.get("role")
        )

        if "cache_invalidation" in result:
            await _invalidate_tenant_cache(db, result["cache_invalidation"])

        return DepartmentResponse(
            id=result["department"]["id"],
            department_name=result["department"]["department_name"],
            description=result["department"]["description"],
            is_active=result["department"]["is_active"],
            agent_count=result["department"]["agent_count"],
            user_count=0, 
            created_at=result["department"]["created_at"],
            tenant_name=result["department"]["tenant_name"],
            agent=result["agent"],
            tool_assignments=result["tool_assignments"]
        )

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Failed to update department: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update department: {str(e)}"
        )


@router.delete("/departments/{department_id}", response_model=OperationResult, summary="Delete department")
async def delete_department(
    department_id: str,
    db: AsyncSession = Depends(get_db),
    user_ctx: dict = Depends(RequireAtLeastAdmin())
) -> OperationResult:
    """Soft delete department (requires ADMIN or higher)"""
    try:
        tenant_id = user_ctx.get("tenant_id")
        user_role = user_ctx.get("role")

        from services.department.department_service import DepartmentService
        dept_service = DepartmentService(db)

        success = await dept_service.delete_department(
            department_id=department_id,
            tenant_id=tenant_id,
            user_role=user_role
        )

        if success:
            await _invalidate_tenant_cache(db, {
                "tenant_id": tenant_id,
                "entity_types": ['departments', 'agents', 'workflow_agents', 'provider_configs', 'provider_api_keys', 'tools']
            })

        return OperationResult(success=success, message="Department deleted successfully")

    except ValueError as e:
            raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Failed to delete department: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete department: {str(e)}"
        )


# ==================== AGENT CRUD ====================

class CreateAgentRequest(BaseModel):
    agent_name: str
    description: str
    department_id: str
    provider_id: Optional[str] = None
    model_id: Optional[str] = None


class AgentResponse(BaseModel):
    id: str
    agent_name: str
    description: str
    department_id: str
    department_name: str
    provider_id: Optional[str]
    model_id: Optional[str]
    is_enabled: bool
    is_system: bool


@router.get("/agents", response_model=List[AgentResponse], summary="List agents")
async def list_agents(
    department_id: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    user_ctx: dict = Depends(RequireAtLeastAdmin())
) -> List[AgentResponse]:
    """List all agents for the tenant, optionally filtered by department"""
    try:
        tenant_id = user_ctx.get("tenant_id")

        from services.agents.agent_service import AgentService
        agent_service = AgentService(db)

        agents_data = await agent_service.get_agents_for_tenant_admin(
            tenant_id=tenant_id,
            department_id=department_id
        )

        response = []
        for agent in agents_data:
            response.append(AgentResponse(**agent))

        return response

    except Exception as e:
        logger.error(f"Failed to list agents: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list agents: {str(e)}"
        )


@router.post("/agents", response_model=AgentResponse, summary="Create agent")
async def create_agent(
    request: CreateAgentRequest,
    db: AsyncSession = Depends(get_db),
    user_ctx: dict = Depends(RequireAtLeastAdmin())
) -> AgentResponse:
    """Create new agent for department"""
    try:
        tenant_id = user_ctx.get("tenant_id")

        from services.agents.agent_service import AgentService
        agent_service = AgentService(db)

        agent_data = await agent_service.create_agent_for_tenant_admin(
            tenant_id=tenant_id,
            department_id=request.department_id,
            agent_name=request.agent_name,
            description=request.description,
            provider_id=request.provider_id,
            model_id=request.model_id
        )

        await _invalidate_tenant_cache(db, {
            "tenant_id": tenant_id,
            "entity_types": [
                'agents', 
                'workflow_agents', 
                'provider_configs', 
                'provider_api_keys'
            ]
        })

        return AgentResponse(**agent_data)

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Failed to create agent: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create agent: {str(e)}"
        )


@router.get("/agents/{agent_id}", response_model=AgentResponse, summary="Get agent")
async def get_agent(
    agent_id: str,
    db: AsyncSession = Depends(get_db),
    user_ctx: dict = Depends(RequireAtLeastAdmin())
) -> AgentResponse:
    """Get agent details"""
    try:
        from services.agents.agent_service import AgentService
        agent_service = AgentService(db)

        agent_data = await agent_service.get_agent_by_id(agent_id)

        if not agent_data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Agent not found"
            )

        return AgentResponse(
            id=agent_data["id"],
            agent_name=agent_data["name"],
            description=agent_data["description"],
            department_id=agent_data["department_id"],
            department_name=agent_data["department_name"],
            provider_id=agent_data.get("provider_id"),
            model_id=agent_data.get("model_id"),
            is_enabled=agent_data["is_enabled"],
            is_system=agent_data["is_system"]
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get agent: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get agent: {str(e)}"
        )


@router.put("/agents/{agent_id}", response_model=AgentResponse, summary="Update agent")
async def update_agent(
    agent_id: str,
    request: CreateAgentRequest,
    db: AsyncSession = Depends(get_db),
    user_ctx: dict = Depends(RequireAtLeastAdmin())
) -> AgentResponse:
    """Update agent details"""
    try:
        tenant_id = user_ctx.get("tenant_id")

        from services.agents.agent_service import AgentService
        agent_service = AgentService(db)

        agent_data = await agent_service.update_agent_for_tenant_admin(
            agent_id=agent_id,
            tenant_id=tenant_id,
            department_id=request.department_id,
            agent_name=request.agent_name,
            description=request.description,
            provider_id=request.provider_id,
            model_id=request.model_id
        )

        await _invalidate_tenant_cache(db, {
            "tenant_id": tenant_id,
            "entity_types": ['agents', 'workflow_agents', 'provider_configs', 'provider_api_keys']
        })

        return AgentResponse(**agent_data)

    except ValueError as e:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Failed to update agent: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update agent: {str(e)}"
        )


@router.delete("/agents/{agent_id}", response_model=OperationResult, summary="Delete agent")
async def delete_agent(
    agent_id: str,
    db: AsyncSession = Depends(get_db),
    user_ctx: dict = Depends(RequireAtLeastAdmin())
) -> OperationResult:
    """Delete agent (requires ADMIN or higher)"""
    try:
        tenant_id = user_ctx.get("tenant_id")
        user_role = user_ctx.get("role")

        from services.agents.agent_service import AgentService
        agent_service = AgentService(db)

        success = await agent_service.delete_agent_for_tenant_admin(
            agent_id=agent_id,
            tenant_id=tenant_id,
            user_role=user_role
        )

        if success:
            await _invalidate_tenant_cache(db, {
                "tenant_id": tenant_id,
                "entity_types": ['agents', 'workflow_agents', 'provider_configs', 'provider_api_keys']
            })

        return OperationResult(success=success, message="Agent deleted successfully")

    except ValueError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Failed to delete agent: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete agent: {str(e)}"
        )


# ==================== TOOL CRUD ====================

class ToolResponse(BaseModel):
    id: str
    tool_name: str
    description: Optional[str]
    category: str
    is_enabled: bool
    is_system: bool
    access_level: str


@router.get("/tools", response_model=List[ToolResponse], summary="List tenant tools")
async def list_tenant_tools(
    db: AsyncSession = Depends(get_db),
    user_ctx: dict = Depends(RequireAtLeastAdmin())
) -> List[ToolResponse]:
    """List all tools available for the tenant"""
    try:
        tenant_id = user_ctx.get("tenant_id")

        from services.tools.tool_service import ToolService
        tool_service = ToolService(db)

        tools_data = await tool_service.get_tools_for_tenant_admin(tenant_id)

        response = []
        for tool in tools_data:
            response.append(ToolResponse(**tool))

        return response

    except Exception as e:
        logger.error(f"Failed to list tenant tools: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list tenant tools: {str(e)}"
        )


@router.post("/tools/{tool_id}/enable", response_model=OperationResult, summary="Enable tool for tenant")
async def enable_tenant_tool(
    tool_id: str,
    is_enabled: bool = True,
    db: AsyncSession = Depends(get_db),
    user_ctx: dict = Depends(RequireAtLeastAdmin())
) -> OperationResult:
    """Enable or disable tool for tenant"""
    try:
        tenant_id = user_ctx.get("tenant_id")

        from services.tools.tool_service import ToolService
        tool_service = ToolService(db)

        message = await tool_service.enable_tool_for_tenant(
                tool_id=tool_id,
            tenant_id=tenant_id,
                is_enabled=is_enabled
            )

        return OperationResult(success=True, message=message)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to enable/disable tool: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to enable/disable tool: {str(e)}"
        )


@router.post("/departments/{department_id}/tools/{tool_id}/enable", response_model=OperationResult, summary="Enable tool for department")
async def enable_department_tool(
    department_id: str,
    tool_id: str,
    is_enabled: bool = True,
    access_level_override: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    user_ctx: dict = Depends(RequireAtLeastAdmin())
) -> OperationResult:
    """Enable or disable tool for department (DEPT_ADMIN or higher)"""
    try:
        tenant_id = user_ctx.get("tenant_id")

        from services.tools.tool_service import ToolService
        tool_service = ToolService(db)

        message = await tool_service.enable_tool_for_department(
                department_id=department_id,
                tool_id=tool_id,
            tenant_id=tenant_id,
                is_enabled=is_enabled,
                access_level_override=access_level_override
            )

        return OperationResult(success=True, message=message)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to enable/disable department tool: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to enable/disable department tool: {str(e)}"
        )