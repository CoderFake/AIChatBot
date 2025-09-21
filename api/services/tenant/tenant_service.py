from typing import List, Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, func
from sqlalchemy.orm import selectinload

from models.database.tenant import Tenant, Department
from models.database.agent import WorkflowAgent, AgentToolConfig, Agent
from models.database.provider import TenantProviderConfig, Provider, ProviderModel
from models.database.tool import TenantToolConfig, Tool
from services.auth.permission_service import PermissionService
from services.cache.redis_service import redis_client
from common.types import DefaultProviderConfig
from utils.logging import get_logger
from core.exceptions import ServiceError
from services.storage.minio_service import MinioService
from common.types import DocumentConstants
from config.settings import get_settings
from utils.datetime_utils import DateTimeManager

logger = get_logger(__name__)

settings = get_settings()

class TenantService:
    """
    Service for tenant management operations with timezone support
    """
    
    def __init__(self, db: AsyncSession):
        self.db = db
        self.permission_service = PermissionService(db)

    async def get_invite_service(self):
        """Get InviteService instance for invitation operations"""
        from services.send_mail.invite_service import InviteService
        return InviteService(self.db)
    
    async def create_tenant(
        self,
        tenant_name: str,
        timezone: str,
        locale: str = "en_US",
        sub_domain: str = None,
        description: Optional[str] = None,
        allowed_providers: Optional[List[str]] = None,
        allowed_tools: Optional[List[str]] = None,
        created_by: str = "system",
    ) -> Dict[str, Any]:
        """
        Create tenant with optional provider and tools setup in single transaction
        """
        try:
            tenant = Tenant(
                tenant_name=tenant_name,
                timezone=timezone,
                locale=locale,
                sub_domain=sub_domain,
                description=description,
                settings={},
                created_by=created_by
            )
            
            self.db.add(tenant)
            await self.db.flush()  

            try:
                minio = MinioService()
                await minio.ensure_bucket(
                    DocumentConstants.BUCKET_NAME_TEMPLATE.format(
                        prefix=settings.storage.bucket_prefix,
                        tenant_id=str(tenant.id)
                    )
                )
            except Exception as storage_exc:
                logger.error(f"Create tenant bucket failed: {storage_exc}")
                raise
            
            default_groups = await self.permission_service.create_default_groups_for_tenant(
                tenant_id=tenant.id,
                created_by=created_by
            )

            tenant_id = str(tenant.id)
            setup_results = {
                "allowed_providers": None,
                "tools_setup": None
            }

            if allowed_providers:

                created_configs = []
                for provider_name in allowed_providers:
                    provider_result = await self.db.execute(
                        select(Provider).where(Provider.provider_name == provider_name)
                    )
                    provider = provider_result.scalar_one_or_none()

                    if provider:
                        config = TenantProviderConfig(
                            tenant_id=tenant_id,
                            provider_id=provider.id,
                            api_keys=[],
                            current_key_index=0,
                            rotation_strategy="round_robin",
                            is_enabled=True,
                            configured_by=created_by
                        )
                        self.db.add(config)
                        await self.db.flush()
                        created_configs.append({
                            "provider_name": provider_name,
                            "config_id": str(config.id)
                        })
                    else:
                        logger.warning(f"Provider {provider_name} not found, skipping")

                setup_results["allowed_providers"] = {
                    "tenant_id": tenant_id,
                    "allowed_providers": allowed_providers,
                    "created_configs": created_configs
                }

            if allowed_tools:

                logger.info(f"Setting up tools for tenant {tenant_name}: {allowed_tools}")

                tools_result = await self.db.execute(
                    select(Tool).where(Tool.id.in_(allowed_tools))
                )
                available_tools = {str(tool.id): tool for tool in tools_result.scalars().all()}
                logger.info(f"Found {len(available_tools)} available tools out of {len(allowed_tools)} requested")

                enabled_tools = []
                for tool_id in allowed_tools:
                    tool_id_str = str(tool_id)
                    if tool_id_str not in available_tools:
                        logger.warning(f"Tool {tool_id} not found in available tools, skipping")
                        continue

                    tool = available_tools[tool_id_str]
                    logger.info(f"Processing tool: {tool.tool_name} (ID: {tool.id})")

                    config_result = await self.db.execute(
                        select(TenantToolConfig).where(
                            (TenantToolConfig.tenant_id == tenant_id) &
                            (TenantToolConfig.tool_id == tool.id)
                        )
                    )
                    existing_config = config_result.scalar_one_or_none()

                    if existing_config:
                        logger.info(f"Updating existing config for tool {tool.tool_name}")
                        existing_config.is_enabled = True
                        existing_config.updated_by = created_by
                        config = existing_config
                    else:
                        logger.info(f"Creating new config for tool {tool.tool_name}")
                        config = TenantToolConfig(
                            tenant_id=tenant_id,
                            tool_id=tool.id,
                            is_enabled=True,
                            config_data={},
                            configured_by=created_by
                        )
                        self.db.add(config)
                        await self.db.flush()

                    enabled_tools.append({
                        "tool_name": tool.tool_name,
                        "config_id": str(config.id)
                    })

                logger.info(f"Successfully set up {len(enabled_tools)} tools for tenant {tenant_name}")
                setup_results["tools_setup"] = {
                    "tenant_id": tenant_id,
                    "enabled_tools": enabled_tools,
                    "total_enabled": len(enabled_tools)
                }

            await self.db.commit()

            await self.invalidate_tenant_caches(tenant.id)
            await DateTimeManager.tenant_now_cached(tenant.id, self.db)

            result = {
                "tenant_id": tenant_id,
                "tenant_name": tenant.tenant_name,
                "timezone": tenant.timezone,
                "locale": tenant.locale,
                "sub_domain": tenant.sub_domain,
                "description": tenant.description,
                "default_groups": default_groups,
                "created_at": tenant.created_at.isoformat(),
                "setup_results": setup_results
            }

            logger.info(f"Successfully created tenant {tenant_name} with setup: providers={len(allowed_providers) if allowed_providers else 0}, tools={len(allowed_tools) if allowed_tools else 0}")

            return result

        except Exception as e:
            logger.error(f"Failed to create tenant with setup: {e}")
            await self.db.rollback()
            raise ServiceError(f"Failed to create tenant with setup: {str(e)}")

    async def get_provider_models(self, provider_name: str) -> Dict[str, Any]:
        """
        Get list of available models for a specific provider
        """
        try:

            provider_result = await self.db.execute(
                select(Provider).where(Provider.provider_name.ilike(f"%{provider_name}%"))
            )
            provider = provider_result.scalar_one_or_none()

            if not provider:
                raise ServiceError(f"Provider '{provider_name}' not found")

            models_result = await self.db.execute(
                select(ProviderModel).where(
                    ProviderModel.provider_id == provider.id,
                    ProviderModel.is_enabled
                )
            )
            models = models_result.scalars().all()

            return {
                "provider": provider.provider_name,
                "models": [
                    {
                        "name": model.model_name,
                        "display_name": model.model_name,
                        "description": f"{model.model_name} model",
                        "model_type": model.model_type
                    }
                    for model in models
                ]
            }

        except Exception as e:
            logger.error(f"Failed to get provider models for {provider_name}: {e}")
            raise ServiceError(f"Failed to get provider models: {str(e)}")

    async def configure_tenant_provider(
        self,
        tenant_id: str,
        provider_name: str,
        model_name: str,
        api_keys: List[str],
        model_config: Optional[Dict[str, Any]] = None,
        configured_by: str = "system"
    ) -> Dict[str, Any]:
        """
        Configure provider with API keys for tenant
        """
        try:
            tenant_result = await self.db.execute(select(Tenant).where(Tenant.id == tenant_id))
            tenant = tenant_result.scalar_one_or_none()
            if not tenant:
                raise ServiceError(f"Tenant not found: {tenant_id}")

            provider_result = await self.db.execute(
                select(Provider).where(Provider.provider_name == provider_name)
            )
            provider = provider_result.scalar_one_or_none()
            if not provider:
                raise ServiceError(f"Provider not found: {provider_name}")

            model_result = await self.db.execute(
                select(ProviderModel).where(
                    (ProviderModel.provider_id == provider.id) &
                    (ProviderModel.model_name == model_name)
                )
            )
            model = model_result.scalar_one_or_none()
            if not model:
                raise ServiceError(f"Model {model_name} not found for provider {provider_name}")

            config_result = await self.db.execute(
                select(TenantProviderConfig).where(
                    (TenantProviderConfig.tenant_id == tenant_id) &
                    (TenantProviderConfig.provider_id == provider.id)
                )
            )
            existing_config = config_result.scalar_one_or_none()

            if existing_config:
                existing_config.api_keys = api_keys
                existing_config.model_config = model_config
                existing_config.configured_by = configured_by
                config = existing_config
            else:
                config = TenantProviderConfig(
                    tenant_id=tenant_id,
                    provider_id=provider.id,
                    api_keys=api_keys,
                    current_key_index=0,
                    rotation_strategy="round_robin",
                    is_enabled=True,
                    config_data=model_config or {},
                    configured_by=configured_by
                )
                self.db.add(config)

            await self.db.flush()
            await self.db.commit()

            logger.info(f"Configured provider {provider_name} for tenant {tenant_id}")
            return {
                "config_id": str(config.id),
                "tenant_id": tenant_id,
                "provider_name": provider_name,
                "model_name": model_name,
                "api_keys_count": len(api_keys),
                "is_enabled": config.is_enabled
            }

        except Exception as e:
            await self.db.rollback()
            logger.error(f"Failed to configure tenant provider: {e}")
            raise ServiceError(f"Failed to configure provider: {str(e)}")

    async def create_workflow_agent_with_provider(
        self,
        tenant_id: str,
        provider_name: str,
        model_name: str,
        model_config: Optional[Dict[str, Any]] = None,
        created_by: str = "system"
    ) -> Dict[str, Any]:
        """
        Create WorkflowAgent with configured provider
        """
        try:
            config_result = await self.db.execute(
                select(TenantProviderConfig)
                .join(Provider, Provider.id == TenantProviderConfig.provider_id)
                .where(
                    (TenantProviderConfig.tenant_id == tenant_id) &
                    (Provider.provider_name == provider_name) &
                    (TenantProviderConfig.is_enabled)
                )
            )
            provider_config = config_result.scalar_one_or_none()

            if not provider_config:
                raise ServiceError(f"No active provider config found for {provider_name} in tenant {tenant_id}")

            existing_result = await self.db.execute(
                select(WorkflowAgent).where(WorkflowAgent.tenant_id == tenant_id)
            )
            existing_agent = existing_result.scalar_one_or_none()

            if existing_agent:
                existing_agent.provider_name = provider_name
                existing_agent.model_name = model_name
                existing_agent.model_config = model_config or existing_agent.model_config
                existing_agent.updated_by = created_by
                wf = existing_agent
            else:
                wf = WorkflowAgent(
                    tenant_id=tenant_id,
                    provider_name=provider_name,
                    model_name=model_name,
                    model_config=model_config or {
                        "temperature": 0.7,
                        "max_tokens": 2048,
                        "top_p": 0.9,
                    },
                    max_iterations=10,
                    timeout_seconds=300,
                    confidence_threshold=0.7,
                    created_by=created_by,
                )
                self.db.add(wf)

            await self.db.flush()
            await self.db.commit()

            logger.info(f"Created/Updated WorkflowAgent for tenant {tenant_id} with provider {provider_name}")
            return {
                "workflow_agent_id": str(wf.id),
                "tenant_id": str(tenant_id),
                "provider_name": wf.provider_name,
                "model_name": wf.model_name,
                "model_config": wf.model_config,
                "max_iterations": wf.max_iterations,
                "timeout_seconds": wf.timeout_seconds,
                "confidence_threshold": wf.confidence_threshold,
                "status": "configured"
            }

        except Exception as e:
            await self.db.rollback()
            logger.error(f"Failed to create workflow agent with provider: {e}")
            raise ServiceError(f"Failed to create workflow agent: {str(e)}")

    async def enable_tenant_tools(
        self,
        tenant_id: str,
        tool_ids: List[str],
        enabled_by: str
    ) -> Dict[str, Any]:
        """
        Enable tools for tenant
        """
        try:
            tools_result = await self.db.execute(
                select(Tool).where(Tool.id.in_(tool_ids))
            )
            available_tools = {tool.id: tool for tool in tools_result.scalars().all()}

            enabled_tools = []
            for tool_id in tool_ids:
                if tool_id not in available_tools:
                    logger.warning(f"Tool {tool_id} not found, skipping")
                    continue

                tool = available_tools[tool_id]

                config_result = await self.db.execute(
                    select(TenantToolConfig).where(
                        (TenantToolConfig.tenant_id == tenant_id) &
                        (TenantToolConfig.tool_id == tool.id)
                    )
                )
                existing_config = config_result.scalar_one_or_none()

                if existing_config:
                    existing_config.is_enabled = True
                    existing_config.updated_by = enabled_by
                    config = existing_config
                else:
                    config = TenantToolConfig(
                        tenant_id=tenant_id,
                        tool_id=tool.id,
                        is_enabled=True,
                        config_data={},
                        configured_by=enabled_by
                    )
                    self.db.add(config)

                enabled_tools.append({
                    "tool_name": tool.tool_name,
                    "config_id": str(config.id)
                })

            await self.db.flush()
            await self.db.commit()

            logger.info(f"Enabled {len(enabled_tools)} tools for tenant {tenant_id}")
            return {
                "tenant_id": tenant_id,
                "enabled_tools": enabled_tools,
                "total_enabled": len(enabled_tools)
            }

        except Exception as e:
            await self.db.rollback()
            logger.error(f"Failed to enable tenant tools: {e}")
            raise ServiceError(f"Failed to enable tools: {str(e)}")

    async def enable_department_tools(
        self,
        department_id: str,
        tool_ids: List[str],
        enabled_by: str
    ) -> Dict[str, Any]:
        """
        Enable tools for department
        """
        try:
            dept_result = await self.db.execute(select(Department).where(Department.id == department_id))
            department = dept_result.scalar_one_or_none()
            if not department:
                raise ServiceError(f"Department not found: {department_id}")

            tools_result = await self.db.execute(
                select(Tool).where(Tool.id.in_(tool_ids))
            )
            available_tools = {tool.id: tool for tool in tools_result.scalars().all()}

            agents_result = await self.db.execute(
                select(Agent).where(Agent.department_id == department_id)
            )
            department_agents = agents_result.scalars().all()

            if not department_agents:
                raise ServiceError(f"No agents found in department {department_id}")

            enabled_tools = []
            for tool_id in tool_ids:
                if tool_id not in available_tools:
                    logger.warning(f"Tool {tool_id} not found, skipping")
                    continue

                tool = available_tools[tool_id]

                agent_configs_created = []
                for agent in department_agents:
                    config_result = await self.db.execute(
                        select(AgentToolConfig).where(
                            (AgentToolConfig.agent_id == agent.id) &
                            (AgentToolConfig.tool_id == tool.id)
                        )
                    )
                    existing_config = config_result.scalar_one_or_none()

                    if existing_config:
                        existing_config.is_enabled = True
                        existing_config.updated_by = enabled_by
                        config = existing_config
                    else:
                        config = AgentToolConfig(
                            agent_id=agent.id,
                            tool_id=tool.id,
                            is_enabled=True,
                            config_data={},
                            usage_limits={},
                            configured_by=enabled_by
                        )
                        self.db.add(config)

                    agent_configs_created.append({
                        "agent_id": str(agent.id),
                        "agent_name": agent.agent_name,
                        "config_id": str(config.id)
                    })

                enabled_tools.append({
                    "tool_id": str(tool.id),
                    "tool_name": tool.tool_name,
                    "agent_configs": agent_configs_created,
                    "is_enabled": True
                })

            await self.db.flush()
            await self.db.commit()

            logger.info(f"Enabled {len(enabled_tools)} tools for department {department_id}")
            return {
                "department_id": department_id,
                "enabled_tools": enabled_tools,
                "total_enabled": len(enabled_tools)
            }

        except Exception as e:
            await self.db.rollback()
            logger.error(f"Failed to enable department tools: {e}")
            raise ServiceError(f"Failed to enable tools: {str(e)}")

    async def create_default_workflow_agent(
        self,
        tenant_id: str,
        provider_name: Optional[str] = None,
        model_name: Optional[str] = None,
        model_config: Optional[Dict[str, Any]] = None,
        created_by: str = "system",
    ) -> Dict[str, Any]:
        """
        Create default WorkflowAgent for a tenant (separate step after tenant creation).
        If parameters are not provided, use DefaultProviderConfig.
        """
        try:
            result = await self.db.execute(select(Tenant).where(Tenant.id == tenant_id))
            tenant = result.scalar_one_or_none()
            if not tenant:
                raise ServiceError(f"Tenant not found: {tenant_id}")

            wf = WorkflowAgent(
                tenant_id=tenant_id,
                provider_name=provider_name or DefaultProviderConfig.PROVIDER_NAME.value,
                model_name=model_name or DefaultProviderConfig.DEFAULT_MODEL.value,
                model_config=model_config or {
                    "temperature": DefaultProviderConfig.DEFAULT_TEMPERATURE,
                    "max_tokens": DefaultProviderConfig.DEFAULT_MAX_TOKENS,
                    "top_p": DefaultProviderConfig.DEFAULT_TOP_P,
                },
                max_iterations=10,
                timeout_seconds=300,
                confidence_threshold=0.7,
                created_by=created_by,
            )

            self.db.add(wf)
            await self.db.flush()
            await self.db.commit()

            logger.info(f"Created WorkflowAgent for tenant {tenant_id}")
            return {
                "workflow_agent_id": str(wf.id),
                "tenant_id": str(tenant_id),
                "provider_name": wf.provider_name,
                "model_name": wf.model_name,
                "model_config": wf.model_config,
                "max_iterations": wf.max_iterations,
                "timeout_seconds": wf.timeout_seconds,
                "confidence_threshold": wf.confidence_threshold,
            }
        except Exception as e:
            await self.db.rollback()
            logger.error(f"Failed to create default WorkflowAgent for tenant {tenant_id}: {e}")
            raise ServiceError(f"Failed to create workflow agent: {str(e)}")
    
    async def get_tenant_by_id(self, tenant_id: str) -> Dict[str, Any]:
        """
        Get full tenant detail by ID including workflow agent and user counters.
        Uses caching to improve performance.
        """
        from services.cache.cache_manager import cache_manager
        
        cache_key = f"tenant_config_{tenant_id}"
        
        try:
            cached_result = await cache_manager.get(cache_key)
            if cached_result is not None:
                logger.debug(f"Cache hit for tenant details: {tenant_id}")
                return cached_result
            
            from services.tenant.settings_service import SettingsService
            settings_service = SettingsService(self.db)

            tenant = await settings_service.get_tenant_settings_with_mapping(tenant_id)
           
            await self.invalidate_tenant_caches(tenant_id)
            logger.debug(f"Cached tenant details for: {tenant_id}")

            return tenant
            
        except Exception as e:
            logger.error(f"Failed to get tenant {tenant_id}: {e}")
            return None
    
    async def update_tenant(
        self,
        tenant_id: str,
        updates: Dict[str, Any],
        updated_by: str
    ) -> bool:
        """
        Update tenant information including timezone.
        Invalidates cache after successful update.
        """
        try:
            if "timezone" in updates:
                logger.info(f"Updating timezone for tenant {tenant_id} to {updates['timezone']}")

            updates["updated_by"] = updated_by

            tenant_updates = {k: v for k, v in updates.items()
                            if k not in ["allowed_providers", "allowed_tools"]}

            await self.db.execute(
                update(Tenant)
                .where(Tenant.id == tenant_id)
                .values(**tenant_updates)
            )

            if "allowed_providers" in updates and updates["allowed_providers"] is not None:

                # Get existing configs with provider names in one query
                existing_configs_result = await self.db.execute(
                    select(TenantProviderConfig, Provider.provider_name)
                    .join(Provider, Provider.id == TenantProviderConfig.provider_id)
                    .where(TenantProviderConfig.tenant_id == tenant_id)
                )
                existing_configs = {}
                provider_names = {}
                for config, provider_name in existing_configs_result.all():
                    existing_configs[config.provider_id] = config
                    provider_names[config.provider_id] = provider_name

                created_configs = []
                for provider_name in updates["allowed_providers"]:
                    provider_result = await self.db.execute(
                        select(Provider).where(Provider.provider_name == provider_name)
                    )
                    provider = provider_result.scalar_one_or_none()

                    if provider:
                        if provider.id in existing_configs:
                            existing_configs[provider.id].is_enabled = True
                            existing_configs[provider.id].updated_by = updated_by
                            config = existing_configs[provider.id]
                        else:
                            config = TenantProviderConfig(
                                tenant_id=tenant_id,
                                provider_id=provider.id,
                                api_keys=[],
                                current_key_index=0,
                                rotation_strategy="round_robin",
                                is_enabled=True,
                                configured_by=updated_by
                            )
                            self.db.add(config)
                            await self.db.flush()

                        created_configs.append({
                            "provider_name": provider_name,
                            "config_id": str(config.id),
                            "action": "updated" if provider.id in existing_configs else "created"
                        })
                    else:
                        logger.warning(f"Provider {provider_name} not found, skipping")

                for config in existing_configs.values():
                    provider_name = provider_names.get(config.provider_id)
                    if provider_name and provider_name not in updates["allowed_providers"]:
                        config.is_enabled = False
                        config.updated_by = updated_by

            if "allowed_tools" in updates and updates["allowed_tools"] is not None:

                logger.info(f"Updating tools for tenant {tenant_id}: {updates['allowed_tools']}")

                existing_tool_configs_result = await self.db.execute(
                    select(TenantToolConfig).where(TenantToolConfig.tenant_id == tenant_id)
                )
                existing_tool_configs = {config.tool_id: config for config in existing_tool_configs_result.scalars().all()}

                tools_result = await self.db.execute(
                    select(Tool).where(Tool.id.in_(updates["allowed_tools"]))
                )
                available_tools = {str(tool.id): tool for tool in tools_result.scalars().all()}

                enabled_tools = []
                for tool_id in updates["allowed_tools"]:
                    tool_id_str = str(tool_id)
                    if tool_id_str not in available_tools:
                        logger.warning(f"Tool {tool_id} not found in available tools, skipping")
                        continue

                    tool = available_tools[tool_id_str]

                    if tool.id in existing_tool_configs:
                        existing_tool_configs[tool.id].is_enabled = True
                        existing_tool_configs[tool.id].updated_by = updated_by
                        config = existing_tool_configs[tool.id]
                    else:
                        config = TenantToolConfig(
                            tenant_id=tenant_id,
                            tool_id=tool.id,
                            is_enabled=True,
                            config_data={},
                            configured_by=updated_by
                        )
                        self.db.add(config)
                        await self.db.flush()

                    enabled_tools.append({
                        "tool_name": tool.tool_name,
                        "config_id": str(config.id),
                        "action": "updated" if tool.id in existing_tool_configs else "created"
                    })

                for config in existing_tool_configs.values():
                    if str(config.tool_id) not in [str(tid) for tid in updates["allowed_tools"]]:
                        config.is_enabled = False
                        config.updated_by = updated_by

                logger.info(f"Successfully updated {len(enabled_tools)} tools for tenant {tenant_id}")

            await self.db.commit()

            await self.invalidate_tenant_caches(tenant_id)
            await DateTimeManager.tenant_now_cached(tenant_id)

            logger.info(f"Updated tenant {tenant_id}")
            return True

        except Exception as e:
            await self.db.rollback()
            logger.error(f"Failed to update tenant {tenant_id}: {e}")
            raise

    async def get_tenant_with_config(self, tenant_id: str) -> Dict[str, Any]:
        """
        Get tenant detail with allowed providers and tools configuration
        """
        try:
            result = await self.db.execute(select(Tenant).where(Tenant.id == tenant_id))
            tenant = result.scalar_one_or_none()
            if not tenant:
                raise ServiceError(f"Tenant not found: {tenant_id}")

            provider_result = await self.db.execute(
                select(Provider.provider_name)
                .join(TenantProviderConfig, Provider.id == TenantProviderConfig.provider_id)
                .where(
                    (TenantProviderConfig.tenant_id == tenant_id) &
                    (TenantProviderConfig.is_enabled)
                )
            )
            allowed_providers = [row[0] for row in provider_result.all()]

            tool_result = await self.db.execute(
                select(Tool.id)
                .join(TenantToolConfig, Tool.id == TenantToolConfig.tool_id)
                .where(
                    (TenantToolConfig.tenant_id == tenant_id) &
                    (TenantToolConfig.is_enabled)
                )
            )
            allowed_tools = [str(row[0]) for row in tool_result.all()]

            return {
                "id": str(tenant.id),
                "tenant_id": str(tenant.id),
                "tenant_name": tenant.tenant_name,
                "timezone": tenant.timezone,
                "locale": tenant.locale,
                "sub_domain": tenant.sub_domain,
                "is_active": tenant.is_active,
                "description": tenant.description,
                "allowed_providers": allowed_providers,
                "allowed_tools": allowed_tools,
                "created_at": tenant.created_at.isoformat() if tenant.created_at else None,
                "updated_at": tenant.updated_at.isoformat() if tenant.updated_at else None,
                "status": "active" if tenant.is_active else "inactive",
                "settings": tenant.settings or {},
            }

        except Exception as e:
            logger.error(f"Failed to get tenant with config {tenant_id}: {e}")
            raise
    
    async def update_workflow_agent(
        self,
        tenant_id: str,
        workflow_config: Dict[str, Any],
        updated_by: str
    ) -> bool:
        """
        Update WorkflowAgent configuration for tenant.
        Invalidates tenant details cache since workflow agent is included in tenant details.
        """
        from services.cache.cache_manager import cache_manager
        
        try:
            await self.db.execute(
                update(WorkflowAgent)
                .where(WorkflowAgent.tenant_id == tenant_id)
                .values(**workflow_config, updated_by=updated_by)
            )
            
            await self.db.commit()
            
            cache_key = f"tenant:{tenant_id}:details"
            try:
                await cache_manager.delete(cache_key)
                logger.debug(f"Invalidated tenant details cache after workflow agent update: {tenant_id}")
            except Exception as cache_error:
                logger.warning(f"Could not invalidate tenant details cache for tenant {tenant_id}: {cache_error}")
            
            try:
                await redis_client.delete_tenant_data(tenant_id)
            except Exception:
                pass
            
            logger.info(f"Updated WorkflowAgent for tenant {tenant_id}")
            return True
            
        except Exception as e:
            await self.db.rollback()
            logger.error(f"Failed to update WorkflowAgent for tenant {tenant_id}: {e}")
            raise ServiceError(f"Failed to update workflow configuration: {str(e)}")

    async def get_workflow_config(self, tenant_id: str) -> Optional[Dict[str, Any]]:
        """
        Get WorkflowAgent configuration for tenant
        """
        try:
            result = await self.db.execute(
                select(WorkflowAgent)
                .where(WorkflowAgent.tenant_id == tenant_id)
            )
            workflow_agent = result.scalar_one_or_none()
            
            if not workflow_agent:
                return None
            
            return workflow_agent.get_workflow_config()
            
        except Exception as e:
            logger.error(f"Failed to get workflow config for tenant {tenant_id}: {e}")
            return None
    
    async def list_tenants(
        self,
        page: int = 1,
        limit: int = 20,
        is_active: Optional[bool] = None
    ) -> Dict[str, Any]:
        """
        List tenants with pagination
        """
        try:
            base_query = select(Tenant)
            if is_active is not None:
                base_query = base_query.where(Tenant.is_active == is_active)

            count_stmt = select(func.count()).select_from(base_query.subquery())
            count_result = await self.db.execute(count_stmt)
            total = count_result.scalar() or 0

            data_query = base_query.options(selectinload(Tenant.workflow_agent))
            data_query = data_query.offset((page - 1) * limit).limit(limit)
            result = await self.db.execute(data_query)
            tenants = result.scalars().all()
            
            tenant_list = []
            for tenant in tenants:
                tenant_data = {
                    "id": str(tenant.id),
                    "tenant_name": tenant.tenant_name,
                    "timezone": tenant.timezone,
                    "locale": tenant.locale,
                    "is_active": tenant.is_active,
                        "sub_domain": tenant.sub_domain,
                    "created_at": tenant.created_at.isoformat(),
                    "workflow_agent_active": tenant.workflow_agent.is_active if tenant.workflow_agent else False
                }
                tenant_list.append(tenant_data)
            
            return {
                "tenants": tenant_list,
                "total": total,
                "page": page,
                "limit": limit,
                "has_more": total > (page * limit)
            }
            
        except Exception as e:
            logger.error(f"Failed to list tenants: {e}")
            raise ServiceError(f"Failed to list tenants: {str(e)}")

    async def get_tenant_public_info(self, tenant_id: str) -> Optional[Dict[str, Any]]:
        """
        Get public tenant information (no authentication required)
        Returns only basic info for login pages
        """
        try:
            query = select(Tenant).where(Tenant.id == tenant_id, Tenant.is_active.is_(True))
            result = await self.db.execute(query)
            tenant = result.scalar_one_or_none()

            if not tenant:
                return None

            logo_url = None
            primary_color = None

            if tenant.settings and isinstance(tenant.settings, dict):
                if "branding" in tenant.settings and isinstance(tenant.settings["branding"], dict):
                    logo_url = tenant.settings["branding"].get("logo_url")
                    primary_color = tenant.settings["branding"].get("primary_color")

                elif "logo_url" in tenant.settings:
                    logo_url = tenant.settings.get("logo_url")
                    primary_color = tenant.settings.get("primary_color")

            return {
                "id": str(tenant.id),
                "tenant_name": tenant.tenant_name,
                "locale": tenant.locale,
                "is_active": tenant.is_active,
                "description": tenant.description,
                "sub_domain": tenant.sub_domain,
                "logo_url": logo_url,
                "primary_color": primary_color or "#6366f1",
            }

        except Exception as e:
            logger.error(f"Failed to get tenant public info: {e}")
            raise ServiceError(f"Failed to get tenant public info: {str(e)}")

    async def invalidate_tenant_caches(
        self,
        tenant_id: str,
        entity_types: Optional[List[str]] = None
    ) -> None:
        """
        Invalidate tenant-related caches for specific entity types to ensure data consistency
        This should be called after any tenant-level changes

        Args:
            tenant_id: Tenant ID to invalidate caches for
            entity_types: List of entity types to invalidate caches for.
            If None, invalidate all tenant caches.
            Supported: 'departments', 'providers', 'provider_configs', 'provider_api_keys', 'tools', 'agents', 'workflow_agents', 'documents'
        """
        try:
            from services.cache.cache_manager import cache_manager

            cache_keys_by_entity = {
                'departments': [
                    f"departments_tenant_{tenant_id}",
                    f"departments_by_tenant_{tenant_id}",
                    f"tenant_departments_{tenant_id}",
                ],
                'providers': [
                    f"providers_tenant_{tenant_id}",
                    f"tenant_provider_configs_{tenant_id}",
                    f"available_providers_tenant_{tenant_id}",
                    f"provider_models_tenant_{tenant_id}",
                ],
                'provider_configs': [
                    f"tenant_provider_config:{tenant_id}:*",
                ],
                'provider_api_keys': [
                    f"provider_api_keys_{tenant_id}_*",
                ],
                'workflow_agents': [
                    f"workflow_agent_{tenant_id}",
                ],
                'tools': [
                    f"tools_tenant_{tenant_id}",
                    f"available_tools_tenant_{tenant_id}",
                    f"tenant_tool_configs_{tenant_id}",
                    f"department_tool_configs_{tenant_id}",
                ],
                'agents': [
                    f"tenant:{tenant_id}:agents",
                    f"agents_tenant_{tenant_id}",
                    f"workflow_agent_{tenant_id}",
                ],
                'documents': [
                    f"documents_tenant_{tenant_id}",
                    f"folders_tenant_{tenant_id}",
                    f"tenant_documents_{tenant_id}",
                    f"document_collections_{tenant_id}",
                    f"department_folders_{tenant_id}",
                ]
            }

            if not entity_types:
                entity_types = list(cache_keys_by_entity.keys())

            cache_keys = []
            for entity_type in entity_types:
                if entity_type in cache_keys_by_entity:
                    cache_keys.extend(cache_keys_by_entity[entity_type])
                else:
                    logger.warning(f"Unknown entity type: {entity_type}")

            core_keys = [
                f"tenant_config_{tenant_id}",
                f"tenant:{tenant_id}:details",
            ]
            cache_keys.extend(core_keys)

            cache_keys = list(set(cache_keys))

            pattern_keys = []
            for entity_type in entity_types:
                pattern_keys.extend([
                    f"*{entity_type}*_{tenant_id}",
                    f"{tenant_id}_{entity_type}*",
                ])

                if entity_type == 'provider_configs':
                    pattern_keys.append(f"tenant_provider_config:{tenant_id}:*")
                elif entity_type == 'provider_api_keys':
                    pattern_keys.append(f"provider_api_keys_{tenant_id}_*")

            deleted_count = 0
            for cache_key in cache_keys:
                try:
                    await cache_manager.delete(cache_key)
                    deleted_count += 1
                    logger.debug(f"Invalidated cache key: {cache_key}")
                except Exception as e:
                    logger.debug(f"Could not delete cache key {cache_key}: {e}")

            pattern_deleted_count = 0
            for pattern in pattern_keys:
                try:
                    await cache_manager.delete_pattern(pattern)
                    pattern_deleted_count += 1
                    logger.debug(f"Invalidated cache pattern: {pattern}")
                except Exception as e:
                    logger.debug(f"Could not delete cache pattern {pattern}: {e}")

            if not entity_types or any(et in ['departments', 'groups'] for et in entity_types):
                try:
                    await redis_client.delete_tenant_data(tenant_id)
                except Exception as e:
                    logger.debug(f"Could not invalidate Redis tenant data: {e}")

            if not entity_types or 'agents' in entity_types:
                try:
                    from services.tenant.settings_service import SettingsService
                    settings_service = SettingsService(self.db)
                    await settings_service._invalidate_settings_cache(tenant_id)
                    logger.debug(f"Invalidated settings cache for tenant {tenant_id}")
                except Exception as e:
                    logger.debug(f"Could not invalidate settings cache: {e}")

            logger.info(f"Successfully invalidated {deleted_count} cache keys and {pattern_deleted_count} patterns for tenant {tenant_id}, entities: {entity_types}")

        except Exception as e:
            logger.error(f"Failed to invalidate tenant caches for tenant {tenant_id}: {e}")

    async def get_bot_and_org_info(self, tenant_id: str) -> Dict[str, str]:
        """
        Get bot name, organization name, and description for tenant.
        Uses SettingsService for consistency and better caching.

        Args:
            tenant_id: Tenant ID

        Returns:
            Dict with 'bot_name', 'organization_name', and 'description' keys
        """
        try:
            from services.tenant.settings_service import SettingsService
            settings_service = SettingsService(self.db)
            
            mapped_settings = await settings_service.get_tenant_settings_with_mapping(tenant_id)
            
            return {
                "bot_name": mapped_settings.get("chatbot_name", "AI Assistant"),
                "organization_name": mapped_settings.get("tenant_name", "Organization"),
                "description": mapped_settings.get("description", "")
            }

        except Exception as e:
            logger.error(f"Failed to get bot and org info for tenant {tenant_id}: {e}")
            return {
                "bot_name": "AI Assistant",
                "organization_name": "Organization",
                "description": ""
            }


async def get_tenant_service(db: AsyncSession) -> TenantService:
    """Get TenantService instance"""
    return TenantService(db)