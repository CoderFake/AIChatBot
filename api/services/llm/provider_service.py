from typing import Dict, Any, List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, delete
from sqlalchemy.orm import selectinload

from models.database.tenant import Tenant
from models.database.provider import Provider, ProviderModel
from services.llm.provider_registry import provider_registry
from utils.logging import get_logger

logger = get_logger(__name__)


class ProviderService:
    """Service to sync default provider registry with the database"""

    def __init__(self, db_session: AsyncSession):
        self.db = db_session

    async def initialize(self) -> None:
        """Sync providers and models from registry to database"""
        await self._sync_registry_to_database()

    async def _sync_registry_to_database(self) -> None:
        """Insert or update provider and model definitions"""
        try:
            registry_providers = provider_registry.get_all_providers()

            result = await self.db.execute(select(Provider))
            existing = {p.provider_name: p for p in result.scalars().all()}

            providers_added = 0
            providers_updated = 0

            for name, info in registry_providers.items():
                base_config = info.get("provider_config", {})
                provider = existing.get(name)

                if provider is None:
                    provider = Provider(
                        provider_name=name,
                        base_config=base_config,
                        is_enabled=True,
                    )
                    self.db.add(provider)
                    await self.db.flush()
                    existing[name] = provider
                    providers_added += 1
                    logger.info(f"Added new provider to database: {name}")
                else:
                    provider.base_config = base_config
                    providers_updated += 1
                    logger.debug(f"Updated provider metadata: {name}")

                await self._sync_provider_models(provider.id, info)

            if providers_added > 0 or providers_updated > 0:
                await self.db.commit()
                logger.info(
                    f"Provider registry sync completed - Added: {providers_added}, Updated: {providers_updated}"
                )
        except Exception as exc:
            await self.db.rollback()
            logger.error(f"Failed to sync provider registry to database: {exc}")
            raise

    async def _sync_provider_models(self, provider_id, info: Dict[str, Any]) -> None:
        """Ensure provider models exist in database"""
        result = await self.db.execute(
            select(ProviderModel).where(ProviderModel.provider_id == provider_id)
        )
        existing_models = {m.model_name: m for m in result.scalars().all()}

        for model_name in info.get("models", []):
            if model_name not in existing_models:
                model = ProviderModel(
                    provider_id=provider_id,
                    model_name=model_name,
                    model_type="chat",
                    is_enabled=True,
                )
                self.db.add(model)
            else:
                existing_models[model_name].model_type = "chat"

        await self.db.flush()

    async def get_available_providers(self) -> List[Dict[str, Any]]:
        """
        Get list of available providers for tenant configuration
        """
        try:
            result = await self.db.execute(
                select(Provider)
                .options(selectinload(Provider.models))
                .where(Provider.is_enabled == True)
                .order_by(Provider.provider_name)
            )
            providers = result.scalars().all()

            provider_list = []
            for provider in providers:
                models = [
                    {
                        "model_name": model.model_name,
                        "model_type": model.model_type,
                        "is_enabled": model.is_enabled
                    }
                    for model in provider.models if model.is_enabled
                ]

                provider_list.append({
                    "provider_id": str(provider.id),
                    "provider_name": provider.provider_name,
                    "base_config": provider.base_config,
                    "available_models": models
                })

            return provider_list

        except Exception as e:
            logger.error(f"Failed to get available providers: {e}")
            return []

    # ==================== AGENT MANAGEMENT METHODS ====================

    async def get_all_agents(self) -> List[Dict[str, Any]]:
        """Get all agents across all tenants (MAINTAINER only)"""
        try:
            from models.database.agent import Agent
            from models.database.tenant import Department

            result = await self.db.execute(
                select(Agent)
                .join(Department, Agent.department_id == Department.id)
                .join(Tenant, Department.tenant_id == Tenant.id)
                .order_by(Tenant.tenant_name, Department.department_name, Agent.agent_name)
            )

            agents = []
            for agent in result.scalars().all():
                agents.append({
                    "id": str(agent.id),
                    "agent_name": agent.agent_name,
                    "description": agent.description,
                    "tenant_id": str(agent.tenant_id),
                    "tenant_name": agent.tenant.tenant_name if agent.tenant else None,
                    "department_id": str(agent.department_id),
                    "department_name": agent.department.department_name if agent.department else None,
                    "provider_id": str(agent.provider_id) if agent.provider_id else None,
                    "model_id": str(agent.model_id) if agent.model_id else None,
                    "is_enabled": agent.is_enabled,
                    "is_system": agent.is_system,
                    "created_at": agent.created_at.isoformat() if agent.created_at else None,
                    "updated_at": agent.updated_at.isoformat() if agent.updated_at else None
                })

            return agents

        except Exception as e:
            logger.error(f"Failed to get all agents: {e}")
            return []

    async def get_agent_by_id(self, agent_id: str) -> Optional[Dict[str, Any]]:
        """Get agent by ID with full details"""
        try:
            from models.database.agent import Agent
            from models.database.tenant import Department

            result = await self.db.execute(
                select(Agent)
                .join(Department, Agent.department_id == Department.id)
                .join(Tenant, Department.tenant_id == Tenant.id)
                .where(Agent.id == agent_id)
            )

            agent = result.scalar_one_or_none()
            if not agent:
                return None

            return {
                "id": str(agent.id),
                "agent_name": agent.agent_name,
                "description": agent.description,
                "tenant_id": str(agent.tenant_id),
                "tenant_name": agent.tenant.tenant_name if agent.tenant else None,
                "department_id": str(agent.department_id),
                "department_name": agent.department.department_name if agent.department else None,
                "provider_id": str(agent.provider_id) if agent.provider_id else None,
                "model_id": str(agent.model_id) if agent.model_id else None,
                "is_enabled": agent.is_enabled,
                "is_system": agent.is_system,
                "created_at": agent.created_at.isoformat() if agent.created_at else None,
                "updated_at": agent.updated_at.isoformat() if agent.updated_at else None
            }

        except Exception as e:
            logger.error(f"Failed to get agent {agent_id}: {e}")
            return None

    async def create_agent(self, agent_name: str, provider_id: str, model_name: str,
                          description: Optional[str] = None, config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Create a new agent (MAINTAINER only)"""
        try:
            from models.database.agent import Agent
            from models.database.provider import ProviderModel

            provider_result = await self.db.execute(
                select(Provider).where(Provider.id == provider_id)
            )
            provider = provider_result.scalar_one_or_none()

            model_result = await self.db.execute(
                select(ProviderModel).where(
                    and_(
                        ProviderModel.provider_id == provider_id,
                        ProviderModel.model_name == model_name
                    )
                )
            )
            model = model_result.scalar_one_or_none()

            if not provider or not model:
                raise ValueError("Invalid provider or model")

            agent = Agent(
                agent_name=agent_name,
                description=description or f"System agent: {agent_name}",
                tenant_id=None, 
                department_id=None,  
                provider_id=provider_id,
                model_id=str(model.id),
                is_enabled=False,  
                is_system=True
            )

            self.db.add(agent)
            await self.db.commit()
            await self.db.refresh(agent)

            return {
                "id": str(agent.id),
                "agent_name": agent_name,
                "description": agent.description,
                "provider_id": provider_id,
                "model_id": str(model.id),
                "is_system": True,
                "is_enabled": False
            }

        except Exception as e:
            logger.error(f"Failed to create agent: {e}")
            await self.db.rollback()
            raise

    async def update_agent(self, agent_id: str, agent_name: Optional[str] = None,
                          provider_id: Optional[str] = None, model_name: Optional[str] = None,
                          description: Optional[str] = None, config: Optional[Dict[str, Any]] = None) -> bool:
        """Update agent configuration"""
        try:
            from models.database.agent import Agent
            from models.database.provider import ProviderModel

            result = await self.db.execute(select(Agent).where(Agent.id == agent_id))
            agent = result.scalar_one_or_none()

            if not agent:
                return False

            if agent_name:
                agent.agent_name = agent_name
            if description is not None:
                agent.description = description
            if provider_id:
                agent.provider_id = provider_id

            if model_name and provider_id:
                model_result = await self.db.execute(
                    select(ProviderModel).where(
                        and_(
                            ProviderModel.provider_id == provider_id,
                            ProviderModel.model_name == model_name
                        )
                    )
                )
                model = model_result.scalar_one_or_none()
                if model:
                    agent.model_id = str(model.id)

            await self.db.commit()
            return True

        except Exception as e:
            logger.error(f"Failed to update agent {agent_id}: {e}")
            await self.db.rollback()
            return False

    async def delete_agent_cascade(self, agent_id: str) -> bool:
        """Delete agent and cascade delete related configurations (MAINTAINER only)"""
        try:
            from models.database.agent import Agent, AgentToolConfig
            from models.database.tool import TenantToolConfig

            # Get agent
            result = await self.db.execute(select(Agent).where(Agent.id == agent_id))
            agent = result.scalar_one_or_none()

            if not agent:
                return False

            await self.db.execute(
                delete(AgentToolConfig).where(AgentToolConfig.agent_id == agent_id)
            )

            if agent.tenant_id:
                await self.db.execute(
                    delete(TenantToolConfig).where(
                        and_(
                            TenantToolConfig.tenant_id == agent.tenant_id,
                            TenantToolConfig.tool_id.in_(
                                select(AgentToolConfig.tool_id).where(AgentToolConfig.agent_id == agent_id)
                            )
                        )
                    )
                )

            await self.db.execute(delete(Agent).where(Agent.id == agent_id))

            await self.db.commit()
            return True

        except Exception as e:
            logger.error(f"Failed to delete agent {agent_id} with cascade: {e}")
            await self.db.rollback()
            return False

    async def assign_agent_to_tenant(self, agent_id: str, tenant_id: str) -> bool:
        """Assign system agent to tenant (create department agent)"""
        try:
            from models.database.agent import Agent
            from models.database.tenant import Department

            result = await self.db.execute(select(Agent).where(Agent.id == agent_id))
            system_agent = result.scalar_one_or_none()

            if not system_agent or not system_agent.is_system:
                return False

            tenant_result = await self.db.execute(select(Tenant).where(Tenant.id == tenant_id))
            tenant = tenant_result.scalar_one_or_none()

            if not tenant:
                return False

            dept_result = await self.db.execute(
                select(Department).where(
                    and_(
                        Department.tenant_id == tenant_id,
                        Department.department_name == f"{system_agent.agent_name} Department"
                    )
                )
            )
            department = dept_result.scalar_one_or_none()

            if not department:
                department = Department(
                    tenant_id=tenant_id,
                    department_name=f"{system_agent.agent_name} Department"
                )
                self.db.add(department)
                await self.db.flush()

            dept_agent = Agent(
                agent_name=system_agent.agent_name,
                description=system_agent.description,
                tenant_id=tenant_id,
                department_id=str(department.id),
                provider_id=system_agent.provider_id,
                model_id=system_agent.model_id,
                is_enabled=True,
                is_system=False
            )

            self.db.add(dept_agent)
            await self.db.commit()
            return True

        except Exception as e:
            logger.error(f"Failed to assign agent {agent_id} to tenant {tenant_id}: {e}")
            await self.db.rollback()
            return False

    async def remove_agent_from_tenant(self, agent_id: str, tenant_id: str) -> bool:
        """Remove agent from tenant"""
        try:
            from models.database.agent import Agent

            result = await self.db.execute(
                select(Agent).where(
                    and_(
                        Agent.id == agent_id,
                        Agent.tenant_id == tenant_id
                    )
                )
            )
            agent = result.scalar_one_or_none()

            if not agent:
                return False

            await self.db.execute(delete(Agent).where(Agent.id == agent_id))
            await self.db.commit()
            return True

        except Exception as e:
            logger.error(f"Failed to remove agent {agent_id} from tenant {tenant_id}: {e}")
            await self.db.rollback()
            return False

    async def get_tenant_agents(self, tenant_id: str) -> List[Dict[str, Any]]:
        """Get agents for a specific tenant"""
        try:
            from models.database.agent import Agent
            from models.database.tenant import Department

            result = await self.db.execute(
                select(Agent)
                .join(Department, Agent.department_id == Department.id)
                .where(
                    and_(
                        Agent.tenant_id == tenant_id,
                        Agent.is_enabled == True
                    )
                )
                .order_by(Department.department_name, Agent.agent_name)
            )

            agents = []
            for agent in result.scalars().all():
                agents.append({
                    "id": str(agent.id),
                    "agent_name": agent.agent_name,
                    "description": agent.description,
                    "department_id": str(agent.department_id),
                    "department_name": agent.department.department_name if agent.department else None,
                    "provider_id": str(agent.provider_id) if agent.provider_id else None,
                    "model_id": str(agent.model_id) if agent.model_id else None,
                    "is_enabled": agent.is_enabled,
                    "is_system": agent.is_system
                })

            return agents

        except Exception as e:
            logger.error(f"Failed to get agents for tenant {tenant_id}: {e}")
            return []

async def get_provider_service(db: AsyncSession) -> ProviderService:
    """Get provider service instance"""
    return ProviderService(db)