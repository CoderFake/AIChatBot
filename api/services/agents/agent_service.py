"""
Agent Service
Database-driven agent management service with department CRUD
Provide agents list to Reflection + Semantic Router for intelligent selection
"""

from typing import Dict, List, Optional, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from sqlalchemy.orm import selectinload
from sqlalchemy.exc import SQLAlchemyError
from datetime import datetime
import json
import uuid

from models.database.agent import Agent, AgentToolConfig
from models.database.tenant import Department
from models.database.tool import Tool, TenantToolConfig
from common.types import AccessLevel, UserRole
from utils.logging import get_logger
from utils.datetime_utils import DateTimeManager

logger = get_logger(__name__)


class AgentService:
    """Service for database-driven agent management with department CRUD"""
    
    def __init__(self, db_session: AsyncSession):
        self.db = db_session
        self._agent_cache: Dict[str, Dict[str, Any]] = {}
        self._agents_structure_cache: Dict[str, Dict[str, Any]] = {} 
        self._cache_timestamp: Optional[datetime] = None
        self._cache_ttl = 1800
    
    def _is_cache_valid(self) -> bool:
        """Check if agent cache is still valid"""
        if not self._cache_timestamp:
            logger.debug("Cache invalid: No timestamp set")
            return False
        
        elapsed_seconds = (DateTimeManager._now() - self._cache_timestamp).total_seconds()
        is_valid = elapsed_seconds < self._cache_ttl
        
        if not is_valid:
            logger.debug(f"Cache invalid: Elapsed {elapsed_seconds}s > TTL {self._cache_ttl}s")
        
        return is_valid
    
    async def _refresh_cache(self) -> None:
        """Refresh agent cache from database"""
        try:
            agents = await self.get_all_enabled_agents_raw()
            self._agent_cache = {}
            
            for agent in agents:
                self._agent_cache[str(agent.id)] = {
                    "id": str(agent.id),
                    "name": agent.agent_name,
                    "description": agent.description,
                    "tenant_id": str(agent.tenant_id) if getattr(agent, 'tenant_id', None) else None,
                    "department_id": str(agent.department_id),
                    "department_name": agent.department.department_name if agent.department else None,
                    "provider_id": str(agent.provider_id) if agent.provider_id else None,
                    "provider_name": agent.provider.provider_name if agent.provider else None,
                    "model_id": str(agent.model_id) if agent.model_id else None,
                    "model_name": agent.model.model_name if agent.model else None,
                    "is_enabled": agent.is_enabled,
                    "is_system": agent.is_system,
                    "tools": await self._get_agent_tools(agent.id),
                    "config_data": await self._get_agent_extended_config(agent.id)
                }
            
            self._cache_timestamp = DateTimeManager._now()
            logger.info(f"Agent cache refreshed with {len(self._agent_cache)} agents")
            
        except Exception as e:
            logger.error(f"Failed to refresh agent cache: {e}")
            if not self._agent_cache:
                self._agent_cache = {}
    
    def invalidate_cache(self) -> None:
        """Force cache refresh on next request"""
        self._cache_timestamp = None
        self._agent_cache.clear()
        self._agents_structure_cache.clear()
        logger.info("Agent cache invalidated - all caches cleared")
    
    async def _get_agent_tools(self, agent_id: str) -> List[Dict[str, Any]]:
        """Get tools for specific agent"""
        try:
            result = await self.db.execute(
                select(AgentToolConfig)
                .options(selectinload(AgentToolConfig.tool))
                .join(Tool, AgentToolConfig.tool_id == Tool.id)
                .where(
                    and_(
                        AgentToolConfig.agent_id == agent_id,
                        AgentToolConfig.is_enabled == True,
                        Tool.is_enabled == True
                    )
                )
            )
            tool_configs = result.scalars().all()
            
            tools = []
            for config in tool_configs:
                if getattr(config, "tool", None):
                    tools.append({
                        "id": str(config.tool.id),
                        "name": config.tool.tool_name,
                        "description": config.tool.description,
                        "config": config.config_data or {}
                    })
            return tools
        except Exception as e:
            logger.error(f"Failed to get tools for agent {agent_id}: {e}")
            return []

    async def _get_agent_extended_config(self, agent_id: str) -> Dict[str, Any]:
        """Get extended configuration for agent"""
        try:
            result = await self.db.execute(
                select(Agent).where(Agent.id == agent_id)
            )
            agent = result.scalar_one_or_none()
            
            if not agent:
                return {}
            
            return {
                "provider_id": str(agent.provider_id) if agent.provider_id else None,
                "model_id": str(agent.model_id) if agent.model_id else None,
                "is_system": agent.is_system,
                "is_enabled": agent.is_enabled
            }
        except Exception as e:
            logger.error(f"Failed to get extended config for agent {agent_id}: {e}")
            return {}

    async def _get_allowed_tool_ids_for_agent(self, agent: Agent) -> Optional[set]:
        """Resolve allowed tool IDs from tenant policy (tenant_tool_configs). Return None if not enforceable."""
        try:
            dept_result = await self.db.execute(
                select(Department).where(Department.id == agent.department_id)
            )
            department = dept_result.scalar_one_or_none()
            
            if not department:
                return None
            
            tenant_id = department.tenant_id
            if not tenant_id:
                return None
            
            configs_result = await self.db.execute(
                select(TenantToolConfig).where(
                    and_(
                        TenantToolConfig.tenant_id == tenant_id,
                        TenantToolConfig.is_enabled == True,
                    )
                )
            )
            configs = configs_result.scalars().all()
            
            return {str(cfg.tool_id) for cfg in configs}
        except Exception as e:
            logger.warning(f"Skip tenant allowed tools enforcement due to error: {e}")
            return None

    async def create_agent_for_existing_department(
        self,
        department_id: str,
        agent_name: str,
        description: str,
        provider_id: Optional[str] = None,
        model_id: Optional[str] = None
    ) -> Optional[Agent]:
        """Create agent for existing department"""
        try:
            stmt = select(Department).where(Department.id == department_id)
            result = await self.db.execute(stmt)
            department = result.scalars().first()
            if not department:
                logger.error(f"Department {department_id} not found")
                return None
            
            stmt = select(Agent).where(Agent.department_id == department_id)
            result = await self.db.execute(stmt)
            existing_agent = result.scalars().first()
            if existing_agent:
                logger.warning(f"Agent already exists for department {department.department_name}")
                return existing_agent
            
            agent = Agent(
                agent_name=agent_name,
                description=description,
                tenant_id=str(department.tenant_id),
                department_id=department_id,
                provider_id=provider_id,
                model_id=model_id,
                is_system=False,
                is_enabled=True
            )
            
            self.db.add(agent)
            await self.db.commit()
            await self.db.refresh(agent)
            
            self.invalidate_cache()
            
            logger.info(f"Created agent '{agent_name}' for department '{department.department_name}'")
            return agent
            
        except Exception as e:
            logger.error(f"Failed to create agent for department {department_id}: {e}")
            await self.db.rollback()
            return None
    
    async def get_all_enabled_agents_raw(self) -> List[Agent]:
        """Get all enabled agents from database (raw ORM objects)"""
        try:
            result = await self.db.execute(
                select(Agent)
                .join(Department, Agent.department_id == Department.id)
                .where(Agent.is_enabled.is_(True))
                .options(
                    selectinload(Agent.department),
                    selectinload(Agent.provider),
                    selectinload(Agent.model)
                )
                .order_by(Agent.agent_name)
            )
            return result.scalars().all()
        except Exception as e:
            logger.error(f"Failed to get enabled agents: {e}")
            return []
    
    async def get_all_enabled_agents(self) -> Dict[str, Dict[str, Any]]:
        """Get all enabled agents formatted for orchestrator"""
        if not self._is_cache_valid():
            await self._refresh_cache()
        
        return self._agent_cache.copy()
    
    async def get_agent_by_id(self, agent_id: str) -> Optional[Dict[str, Any]]:
        """Get specific agent by ID"""
        if not self._is_cache_valid():
            await self._refresh_cache()
        
        return self._agent_cache.get(agent_id)
    
    async def get_agents_by_department(self, department_id: str) -> Dict[str, Dict[str, Any]]:
        """Get agents by department ID"""
        if not self._is_cache_valid():
            await self._refresh_cache()

        return {
            agent_id: agent for agent_id, agent in self._agent_cache.items()
            if agent.get("department_id") == department_id
        }

    async def get_agent_tools(self, agent_id: str) -> List[Dict[str, Any]]:
        """Get tools available for specific agent"""
        agent = await self.get_agent_by_id(agent_id)
        return agent.get("tools", []) if agent else []
    
    async def get_agent_config(self, agent_id: str) -> Dict[str, Any]:
        """Get complete agent configuration from database"""
        agent = await self.get_agent_by_id(agent_id)
        if not agent:
            return {}
        
        config = {
            "provider_id": agent.get("provider_id"),
            "provider_name": agent.get("provider_name"),
            "model_id": agent.get("model_id"),
            "model_name": agent.get("model_name"),
            "tools": agent.get("tools", [])
        }
        
        extended_config = agent.get("config_data", {})
        config.update(extended_config)
        
        return config
    
    async def create_agent(
        self,
        agent_name: str,
        description: str,
        department_id: str,
        provider_id: Optional[str] = None,
        model_id: Optional[str] = None,
        is_system: bool = False
    ) -> Optional[Agent]:
        """Create new agent in database"""
        try:
            stmt = select(Department).where(Department.id == department_id)
            result = await self.db.execute(stmt)
            department = result.scalars().first()
            if not department:
                logger.error(f"Department {department_id} not found")
                return None
            
            agent = Agent(
                agent_name=agent_name,
                description=description,
                tenant_id=str(department.tenant_id),
                department_id=department_id,
                provider_id=provider_id,
                model_id=model_id,
                is_system=is_system,
                is_enabled=True
            )
            
            self.db.add(agent)
            await self.db.commit()
            await self.db.refresh(agent)
            
            self._cache_timestamp = None
            
            logger.info(f"Created agent: {agent_name} with ID: {agent.id}")
            return agent
            
        except Exception as e:
            logger.error(f"Failed to create agent {agent_name}: {e}")
            await self.db.rollback()
            return None
    
    async def update_agent_status(self, agent_id: str, is_enabled: bool) -> bool:
        """Enable/disable agent"""
        try:
            stmt = select(Agent).where(Agent.id == agent_id)
            result = await self.db.execute(stmt)
            agent = result.scalars().first()
            if not agent:
                return False
            
            agent.is_enabled = is_enabled
            await self.db.commit()
            
            self._cache_timestamp = None
            
            logger.info(f"Updated agent {agent_id} status to {is_enabled}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to update agent {agent_id}: {e}")
            await self.db.rollback()
            return False
    
    async def assign_tools_to_agent(self, agent_id: str, tool_ids: List[str]) -> bool:
        """Assign tools to agent with tenant-level policy enforcement"""
        try:
            stmt = select(Agent).where(Agent.id == agent_id)
            result = await self.db.execute(stmt)
            agent = result.scalars().first()
            if not agent:
                return False
            
            allowed_ids = await self._get_allowed_tool_ids_for_agent(agent)
            if allowed_ids is not None:
                disallowed = [tid for tid in tool_ids if tid not in allowed_ids]
                if disallowed:
                    logger.error(
                        f"Disallowed tools for agent {agent_id}: {disallowed}. Allowed set size={len(allowed_ids)}"
                    )
                    return False
            
            stmt = select(AgentToolConfig).where(AgentToolConfig.agent_id == agent_id)
            result = await self.db.execute(stmt)
            configs = result.scalars().all()
            for config in configs:
                await self.db.delete(config)
            
            for tool_id in tool_ids:
                stmt = select(Tool).where(and_(Tool.id == tool_id, Tool.is_enabled == True))
                result = await self.db.execute(stmt)
                tool = result.scalars().first()
                if tool:
                    config = AgentToolConfig(
                        agent_id=agent_id,
                        tool_id=tool_id,
                        is_enabled=True
                    )
                    self.db.add(config)
            
            self.db.commit()
        
            self._cache_timestamp = None
            
            logger.info(f"Assigned {len(tool_ids)} tools to agent {agent_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to assign tools to agent {agent_id}: {e}")
            self.db.rollback()
            return False
    
    async def get_stats(self) -> Dict[str, Any]:
        """Get agent statistics"""
        try:
            stmt = select(Agent)
            result = await self.db.execute(stmt)
            total_agents = len(result.scalars().all())

            stmt = select(Agent).where(Agent.is_enabled == True)
            result = await self.db.execute(stmt)
            enabled_agents = len(result.scalars().all())
            
            dept_stats = {}
            stmt = select(Department)
            result = await self.db.execute(stmt)
            departments = result.scalars().all()
            for dept in departments:
                stmt = select(Agent).where(
                    and_(
                        Agent.department_id == str(dept.id),
                        Agent.is_enabled == True
                    )
                )
                result = await self.db.execute(stmt)
                agent_count = len(result.scalars().all())
                dept_stats[str(dept.id)] = {
                    "department_name": dept.department_name,
                    "agent_count": agent_count
                }
            
            return {
                "total_agents": total_agents,
                "enabled_agents": enabled_agents,
                "disabled_agents": total_agents - enabled_agents,
                "agents_by_department": dept_stats,
                "cache_status": "valid" if self._is_cache_valid() else "invalid"
            }
            
        except Exception as e:
            logger.error(f"Failed to get agent stats: {e}")
            return {}
    
    async def create_agent_with_provider(
        self,
        tenant_id: str,
        department_id: str,
        agent_name: str,
        description: str,
        provider_id: str,
        model_id: Optional[str] = None,
        config_data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Create agent with provider configuration and encrypted API keys
        Called by DepartmentService - handles own errors and raises for rollback
        """
        try:
            logger.info(f"Creating agent '{agent_name}' with provider '{provider_id}'")
            
            dept_result = await self.db.execute(
                select(Department).where(
                    and_(
                        Department.id == department_id,
                        Department.tenant_id == tenant_id
                    )
                )
            )
            department = dept_result.scalar_one_or_none()
            
            if not department:
                logger.error(f"Department {department_id} not found in tenant {tenant_id}")
                raise ValueError(f"Department {department_id} not found in tenant {tenant_id}")
            
            agent = Agent(
                agent_name=agent_name,
                description=description,
                tenant_id=tenant_id,
                department_id=department_id,
                provider_id=provider_id,
                model_id=model_id,
                is_system=False,
                is_enabled=True
            )
            self.db.add(agent)
            await self.db.flush()
            logger.info(f"✓ Agent created: {agent.id}")
           
            self.invalidate_cache()
            
            result = {
                "agent": {
                    "id": str(agent.id),
                    "name": agent_name,
                    "description": description,
                    "tenant_id": tenant_id,
                    "department_id": department_id,
                    "provider_id": provider_id,
                    "model_id": model_id,
                    "is_enabled": True
                }
            }
            
            logger.info(f"Created agent {agent_name} with provider config successfully")
            return result
            
        except ValueError as e:
            logger.error(f"Validation error creating agent with provider: {e}")
            raise
        except SQLAlchemyError as e:
            logger.error(f"Database error creating agent with provider: {e}")
            raise RuntimeError(f"Database error creating agent with provider: {e}")
        except Exception as e:
            logger.error(f"Failed to create agent with provider: {e}")
            raise RuntimeError(f"Failed to create agent with provider: {e}")

    async def update_agent_provider_config(
        self, 
        agent_id: str, 
        provider_id: str, 
        model_id: Optional[str] = None,
        api_keys: Optional[List[str]] = None,
        config_data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Update agent with provider configuration and encrypted API keys
        """
        try:
            from services.providers.provider_service import ProviderService
            
            result = await self.db.execute(
                select(Agent).where(Agent.id == agent_id)
            )
            agent = result.scalar_one_or_none()
            
            if not agent:
                logger.error(f"Agent {agent_id} not found")
                raise ValueError(f"Agent {agent_id} not found")
            
            agent.provider_id = provider_id
            if model_id:
                agent.model_id = model_id
            
            await self.db.flush()
            
            provider_service = ProviderService(self.db)
            provider_result = await provider_service.create_or_update_tenant_provider_config(
                tenant_id=agent.tenant_id,
                provider_id=provider_id,
                api_keys=api_keys or [],
                config_data=config_data
            )
            
            self.invalidate_cache()
            
            result = {
                "agent": {
                    "id": str(agent.id),
                    "name": agent.agent_name,
                    "provider_id": provider_id,
                    "model_id": model_id,
                    "updated": True
                },
                "provider_config": provider_result
            }
            
            logger.info(f"Updated agent {agent_id} provider config (provider: {provider_id})")
            return result
            
        except ValueError as e:
            logger.error(f"Validation error updating agent provider config: {e}")
            raise
        except SQLAlchemyError as e:
            logger.error(f"Database error updating agent provider config: {e}")
            raise RuntimeError(f"Database error updating agent provider config: {e}")
        except Exception as e:
            logger.error(f"Failed to update agent provider config: {e}")
            raise RuntimeError(f"Failed to update agent provider config: {e}")

    async def rotate_agent_api_key(self, agent_id: str) -> Optional[str]:
        """
        Rotate API key for agent and return new API key
        """
        try:
            from services.providers.provider_service import ProviderService
            
            result = await self.db.execute(
                select(Agent).where(Agent.id == agent_id)
            )
            agent = result.scalar_one_or_none()
            
            if not agent or not agent.provider_id:
                logger.error(f"Agent {agent_id} not found or no provider configured")
                raise ValueError(f"Agent {agent_id} not found or no provider configured")
            
            provider_service = ProviderService(self.db)
            rotation_result = await provider_service.rotate_api_key(
                tenant_id=agent.tenant_id,
                provider_id=agent.provider_id
            )
            
            logger.info(f"Rotated API key for agent {agent_id}")
            return rotation_result.get("new_api_key")
            
        except ValueError as e:
            logger.error(f"Validation error rotating agent API key: {e}")
            raise
        except SQLAlchemyError as e:
            logger.error(f"Database error rotating agent API key: {e}")
            raise RuntimeError(f"Database error rotating agent API key: {e}")
        except Exception as e:
            logger.error(f"Failed to rotate API key for agent {agent_id}: {e}")
            raise RuntimeError(f"Failed to rotate API key for agent: {e}")

    async def get_api_key_for_agent(self, agent_id: str) -> Optional[str]:
        """
        Get API key for agent - ready for API calls
        """
        try:
            
            result = await self.db.execute(
                select(Agent).where(Agent.id == agent_id)
            )
            agent = result.scalar_one_or_none()
            
            if not agent or not agent.provider_id:
                logger.warning(f"Agent {agent_id} not found or no provider configured")
                return None
            
            from models.database.provider import TenantProviderConfig
            provider_result = await self.db.execute(
                select(TenantProviderConfig).where(
                    TenantProviderConfig.tenant_id == agent.tenant_id,
                    TenantProviderConfig.provider_id == agent.provider_id
                )
            )
            provider_config_db = provider_result.scalar_one_or_none()

            if provider_config_db and provider_config_db.api_keys:
                current_key_index = provider_config_db.current_key_index or 0

                if current_key_index < len(provider_config_db.api_keys):
                    api_key = provider_config_db.api_keys[current_key_index]

                    return api_key
                else:
                    logger.warning(f"No valid API key at index {current_key_index} for agent {agent_id}")
            else:
                logger.warning(f"No provider config found for agent {agent_id}")
            
            return None
            
        except Exception as e:
            logger.error(f"Failed to get API key for agent {agent_id}: {e}")
            return None

    async def get_agent_provider_info(self, agent_id: str) -> Optional[Dict[str, Any]]:
        """
        Get agent provider information (without decrypting API keys)
        """
        try:
            from models.database.provider import TenantProviderConfig, Provider
            
            result = await self.db.execute(
                select(Agent).where(Agent.id == agent_id)
            )
            agent = result.scalar_one_or_none()
            
            if not agent:
                return None
            
            if not agent.provider_id:
                return {"agent_id": agent_id, "provider_configured": False}
            
            provider_result = await self.db.execute(
                select(Provider).where(Provider.id == agent.provider_id)
            )
            provider = provider_result.scalar_one_or_none()
            
            tenant_config_result = await self.db.execute(
                select(TenantProviderConfig).where(
                    and_(
                        TenantProviderConfig.tenant_id == agent.tenant_id,
                        TenantProviderConfig.provider_id == agent.provider_id
                    )
                )
            )
            tenant_config = tenant_config_result.scalar_one_or_none()
            
            result = {
                "agent_id": agent_id,
                "agent_name": agent.agent_name,
                "provider_configured": True,
                "provider_id": str(agent.provider_id),
                "provider_name": provider.provider_name if provider else None,
                "model_id": str(agent.model_id) if agent.model_id else None,
            }
            
            if tenant_config:
                result.update({
                    "key_count": len(tenant_config.api_keys) if tenant_config.api_keys else 0,
                    "current_key_index": tenant_config.current_key_index,
                    "rotation_strategy": tenant_config.rotation_strategy,
                    "is_enabled": tenant_config.is_enabled,
                    "config_data": tenant_config.config_data or {}
                })
            
            return result
            
        except Exception as e:
            logger.error(f"Failed to get agent provider info: {e}")
            return None

    async def execute_agent(
        self,
        agent_name: str,
        query: str,
        tool_name: str,
        user_context: Dict[str, Any],
        detected_language: str = "vietnamese",
        agent_id: str = None,
        agent_providers: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """
        Execute a specific agent with a specific tool using agent's own LLM

        Args:
            agent_name: Name of the agent to execute
            query: The query to process
            tool_name: Name of the tool to use
            user_context: User context including permissions, department, etc.
            detected_language: Detected language for the query
            agent_id: Agent ID to get specific LLM provider
            agent_providers: Dict of agent providers by agent_id

        Returns:
            Dict containing agent execution results
        """
        try:
            agent_config = None
            if agent_id:
                agent_config = await self.get_agent_config_by_id(agent_id, user_context)
            else:
                agents_structure = await self.get_agents_structure_for_user(user_context)
                
                for agent_key, agent_data in agents_structure.items():
                    if isinstance(agent_data, dict):
                        stored_agent_name = agent_data.get("agent_name", agent_key)
                        if stored_agent_name.lower() == agent_name.lower():
                            agent_config = agent_data
                            break

            if not agent_config:
                return {
                    "content": f"Agent {agent_name} not found or not available",
                    "confidence": 0.0,
                    "sources": [],
                    "error": f"Agent {agent_name} not found"
                }
            
            from services.tools.tool_manager import tool_manager

            raw_role = user_context.get("role")
            normalized_role = raw_role.upper() if isinstance(raw_role, str) else ""

            requested_scope = str(user_context.get("access_scope") or AccessLevel.PUBLIC.value).lower()
            if requested_scope not in {AccessLevel.PUBLIC.value, AccessLevel.PRIVATE.value, "both"}:
                requested_scope = AccessLevel.PUBLIC.value

            if normalized_role == UserRole.USER.value:
                requested_scope = AccessLevel.PUBLIC.value

            if requested_scope == "both":
                access_levels = [AccessLevel.PUBLIC.value, AccessLevel.PRIVATE.value]
            elif requested_scope == AccessLevel.PRIVATE.value:
                access_levels = [AccessLevel.PRIVATE.value]
            else:
                access_levels = [AccessLevel.PUBLIC.value]

            department_value = user_context.get("department") or user_context.get("department_name")
            if not department_value:
                department_id = user_context.get("department_id")
                if department_id:
                    dept_lookup_id = department_id
                    if isinstance(dept_lookup_id, str):
                        try:
                            dept_lookup_id = uuid.UUID(dept_lookup_id)
                        except (ValueError, TypeError):
                            dept_lookup_id = department_id
                    dept_result = await self.db.execute(
                        select(Department.department_name).where(Department.id == dept_lookup_id)
                    )
                    department_value = dept_result.scalar_one_or_none()

            if not department_value:
                if normalized_role in {UserRole.ADMIN.value, UserRole.MAINTAINER.value}:
                    department_value = "all"
                else:
                    department_value = "general"

            tool_params = {
                "query": query,
                "department": department_value,
                "user_id": user_context.get("user_id", ""),
                "access_levels": access_levels,
                "access_scope_override": requested_scope,
                "user_role": raw_role
            }
            tool_result = await tool_manager.execute_tool(tool_name, tool_params, agent_providers, agent_id, user_context)

            if isinstance(tool_result, str):
                try:
                    result_data = json.loads(tool_result)
                except json.JSONDecodeError:
                    result_data = {
                        "content": tool_result,
                        "confidence": 0.5,
                        "sources": []
                    }
            else:
                result_data = tool_result if isinstance(tool_result, dict) else {
                    "content": str(tool_result),
                    "confidence": 0.5,
                    "sources": []
                }

            return {
                "content": result_data.get("context", result_data.get("content", "")),
                "confidence": result_data.get("confidence", 0.5),
                "sources": result_data.get("documents", result_data.get("sources", [])),
                "metadata": {
                    "agent_name": agent_name,
                    "tool_used": tool_name,
                    "execution_timestamp": datetime.now().isoformat(),
                    "detected_language": detected_language,
                    "access_scope": user_context.get("access_scope")
                }
            }

        except Exception as e:
            logger.error(f"Failed to execute agent {agent_name} with tool {tool_name}: {e}")
            return {
                "content": f"Failed to execute agent {agent_name}: {str(e)}",
                "confidence": 0.0,
                "sources": [],
                "error": str(e)
            }

    async def get_agents_for_tenant_admin(
        self,
        tenant_id: str,
        department_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Get agents for tenant admin, optionally filtered by department
        """
        try:
            query = select(Agent).where(Agent.tenant_id == tenant_id)
            if department_id:
                query = query.where(Agent.department_id == department_id)

            result = await self.db.execute(
                query.options(selectinload(Agent.department))
            )
            agents = result.scalars().all()

            agent_list = []
            for agent in agents:
                agent_list.append({
                    "id": str(agent.id),
                    "agent_name": agent.agent_name,
                    "description": agent.description,
                    "department_id": str(agent.department_id),
                    "department_name": "",
                    "provider_id": str(agent.provider_id) if agent.provider_id else None,
                    "model_id": str(agent.model_id) if agent.model_id else None,
                    "is_enabled": agent.is_enabled,
                    "is_system": agent.is_system
                })

            return agent_list

        except Exception as e:
            logger.error(f"Failed to get agents for tenant admin: {e}")
            raise

    async def create_agent_for_tenant_admin(
        self,
        tenant_id: str,
        department_id: str,
        agent_name: str,
        description: str,
        provider_id: Optional[str] = None,
        model_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Create agent for tenant admin with validation
        """
        try:
            dept_result = await self.db.execute(
                select(Department).where(
                    Department.id == department_id,
                    Department.tenant_id == tenant_id,
                    Department.is_deleted == False
                )
            )
            department = dept_result.scalar_one_or_none()

            if not department:
                raise ValueError("Department not found")

            agent_result = await self.db.execute(
                select(Agent).where(
                    Agent.tenant_id == tenant_id,
                    Agent.agent_name == agent_name
                )
            )
            existing_agent = agent_result.scalar_one_or_none()

            if existing_agent:
                raise ValueError("Agent name already exists")

            if department.agent:
                raise ValueError("Department already has an agent")

            # Create agent
            agent = Agent(
                tenant_id=tenant_id,
                department_id=department_id,
                agent_name=agent_name,
                description=description,
                provider_id=provider_id,
                model_id=model_id,
                is_enabled=True,
                is_system=False
            )

            self.db.add(agent)
            await self.db.flush()

            return {
                "id": str(agent.id),
                "agent_name": agent.agent_name,
                "description": agent.description,
                "department_id": str(agent.department_id),
                "department_name": department.department_name, 
                "provider_id": str(agent.provider_id) if agent.provider_id else None,
                "model_id": str(agent.model_id) if agent.model_id else None,
                "is_enabled": agent.is_enabled,
                "is_system": agent.is_system
            }

        except Exception as e:
            logger.error(f"Failed to create agent for tenant admin: {e}")
            raise

    async def update_agent_for_tenant_admin(
        self,
        agent_id: str,
        tenant_id: str,
        department_id: str,
        agent_name: str,
        description: str,
        provider_id: Optional[str] = None,
        model_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Update agent for tenant admin with validation
        """
        try:
            result = await self.db.execute(
                select(Agent).where(
                    Agent.id == agent_id,
                    Agent.tenant_id == tenant_id
                )
            )
            agent = result.scalar_one_or_none()

            if not agent:
                raise ValueError("Agent not found")

            agent.agent_name = agent_name
            agent.description = description
            agent.department_id = department_id
            agent.provider_id = provider_id
            agent.model_id = model_id

            await self.db.flush()

            return {
                "id": str(agent.id),
                "agent_name": agent.agent_name,
                "description": agent.description,
                "department_id": str(agent.department_id),
                "department_name": "",  # Department name not loaded to avoid relationship issues
                "provider_id": str(agent.provider_id) if agent.provider_id else None,
                "model_id": str(agent.model_id) if agent.model_id else None,
                "is_enabled": agent.is_enabled,
                "is_system": agent.is_system
            }

        except Exception as e:
            logger.error(f"Failed to update agent for tenant admin: {e}")
            raise

    async def delete_agent_for_tenant_admin(self, agent_id: str, tenant_id: str, user_role: str) -> bool:
        """
        Delete agent for tenant admin with proper permissions
        """
        try:
            if user_role not in ["ADMIN"]:
                raise ValueError("Only ADMIN can delete agents")

            # Get agent
            result = await self.db.execute(
                select(Agent).where(
                    Agent.id == agent_id,
                    Agent.tenant_id == tenant_id
                )
            )
            agent = result.scalar_one_or_none()

            if not agent:
                raise ValueError("Agent not found")

            if agent.is_system:
                raise ValueError("Cannot delete system agent")

            await self.db.delete(agent)
            await self.db.flush()

            return True

        except Exception as e:
            logger.error(f"Failed to delete agent for tenant admin: {e}")
            raise

    async def get_agents_structure_for_user(
        self,
        user_context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Get agents structure with role-based access control and caching

        Args:
            user_context: User context containing tenant_id, role, department_id, etc.

        Returns:
            Dict containing agents structure with tools filtered by role
        """
        tenant_id = user_context.get("tenant_id")
        user_role = user_context.get("role", "user")
        user_department_id = user_context.get("department_id")

        if not tenant_id:
            raise ValueError("Tenant ID is required")

        cache_key = f"agents_structure:{tenant_id}:{user_role}:{user_department_id or 'none'}"

        # Check cache validity with proper logging
        cached_result = self._agents_structure_cache.get(cache_key)
        if cached_result and self._is_cache_valid():
            logger.info(f"Cache HIT: Using cached agents structure for user role: {user_role}, tenant: {tenant_id}")
            return cached_result
        else:
            # Log specific cache miss reason
            if not cached_result:
                logger.info(f"Cache MISS: No cached data for key {cache_key}")
            elif not self._is_cache_valid():
                logger.info(f"Cache MISS: Cache expired for key {cache_key}")
            logger.info(f"Cache MISS: Building agents structure from database for user role: {user_role}, tenant_id: {tenant_id}, department_id: {user_department_id}")


        from models.database.agent import Agent, AgentToolConfig
        from models.database.tool import Tool
        from models.database.tenant import Department
        from sqlalchemy import select, and_, or_

        if user_role == "admin":
            query = select(
                Agent.agent_name,
                Agent.description,
                Agent.id.label("agent_id"),
                Department.department_name,
                AgentToolConfig.access_level_override,
                Tool.tool_name,
                Tool.description.label("tool_description"),
                Tool.category
            ).select_from(
                Agent
            ).join(
                Department, Department.id == Agent.department_id
            ).join(
                AgentToolConfig, AgentToolConfig.agent_id == Agent.id
            ).join(
                Tool, Tool.id == AgentToolConfig.tool_id
            ).where(
                and_(
                    Agent.tenant_id == tenant_id,
                    Agent.is_enabled == True,
                    AgentToolConfig.is_enabled == True,
                    Tool.is_enabled == True,
                    Department.is_active == True
                )
            )

        elif user_role in ["dept_admin", "dept_manager"]:
            query = select(
                Agent.agent_name,
                Agent.description,
                Agent.id.label("agent_id"),
                Department.department_name,
                AgentToolConfig.access_level_override,
                Tool.tool_name,
                Tool.description.label("tool_description"),
                Tool.category
            ).select_from(
                Agent
            ).join(
                Department, Department.id == Agent.department_id
            ).join(
                AgentToolConfig, AgentToolConfig.agent_id == Agent.id
            ).join(
                Tool, Tool.id == AgentToolConfig.tool_id
            ).where(
                and_(
                    Agent.tenant_id == tenant_id,
                    Agent.is_enabled == True,
                    AgentToolConfig.is_enabled == True,
                    Tool.is_enabled == True,
                    Department.is_active == True,
                    or_(
                        Department.id == user_department_id, 
                        AgentToolConfig.access_level_override.in_(["public", "both"]) 
                    )
                )
            )

        else:
            query = select(
                Agent.agent_name,
                Agent.description,
                Agent.id.label("agent_id"),
                Department.department_name,
                AgentToolConfig.access_level_override,
                Tool.tool_name,
                Tool.description.label("tool_description"),
                Tool.category
            ).select_from(
                Agent
            ).join(
                Department, Department.id == Agent.department_id
            ).join(
                AgentToolConfig, AgentToolConfig.agent_id == Agent.id
            ).join(
                Tool, Tool.id == AgentToolConfig.tool_id
            ).where(
                and_(
                    Agent.tenant_id == tenant_id,
                    Agent.is_enabled == True,
                    AgentToolConfig.is_enabled == True,
                    Tool.is_enabled == True,
                    Department.is_active == True,
                    or_(
                        AgentToolConfig.access_level_override.in_(["public", "both"]),
                        AgentToolConfig.access_level_override.is_(None)
                    )
                )
            )

        result = await self.db.execute(query)
        rows = result.all()
        logger.info(f"Query returned {len(rows)} rows for user role {user_role}")
        
        if len(rows) > 0 and not self._is_cache_valid():
            self._cache_timestamp = DateTimeManager._now()
            logger.info("Refreshed cache timestamp due to new query results")

        agents = {}
        for row in rows:
            agent_name = row.agent_name.lower()
            agent_id = str(row.agent_id)
            
            if agent_name not in agents:
                agents[agent_name] = {
                    "agent_name": row.agent_name, 
                    "desc": row.description or "",
                    "agent_id": agent_id,
                    "department": row.department_name or "",
                    "tools": []
                }

            tool_info = {
                "name": row.tool_name,
                "description": row.tool_description or "",
                "access_level": row.access_level_override or "public",
                "category": row.category or ""
            }

            if not any(t["name"] == tool_info["name"] for t in agents[agent_name]["tools"]):
                agents[agent_name]["tools"].append(tool_info)

        self._agents_structure_cache[cache_key] = agents
        if not self._cache_timestamp:
            self._cache_timestamp = DateTimeManager._now()
        logger.info(f"Cached agents structure for user role: {user_role} with {len(agents)} agents, cache key: {cache_key}")

        return agents

    async def get_agent_config_by_id(self, agent_id: str, user_context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Get agent configuration directly by agent_id - more reliable than name matching
        
        Args:
            agent_id: Agent ID to get config for
            user_context: User context for permissions
            
        Returns:
            Dict containing agent configuration or None if not found
        """
        try:
            agents_structure = await self.get_agents_structure_for_user(user_context)
            
            for agent_key, agent_data in agents_structure.items():
                if isinstance(agent_data, dict) and agent_data.get("agent_id") == agent_id:
                    return agent_data
            
            logger.warning(f"Agent config not found for agent_id: {agent_id}")
            return None
            
        except Exception as e:
            logger.error(f"Failed to get agent config by ID {agent_id}: {e}")
            return None

    async def _get_agent_llm_provider(self, agent_id: str, tenant_id: str):
        """
        Get LLM provider specifically configured for an agent

        Args:
            agent_id: Agent ID to get LLM config for
            tenant_id: Tenant ID

        Returns:
            LLM provider instance or None
        """
        try:
            from models.database.agent import Agent
            from models.database.provider import Provider, ProviderModel, TenantProviderConfig
            from sqlalchemy import select, and_
            from services.llm.provider_manager import LLMProviderConfig

            query = select(
                Agent, Provider, ProviderModel, TenantProviderConfig
            ).select_from(
                Agent
            ).join(
                Provider, Provider.id == Agent.provider_id
            ).join(
                ProviderModel, and_(
                    ProviderModel.provider_id == Provider.id,
                    ProviderModel.id == Agent.model_id
                )
            ).join(
                TenantProviderConfig, and_(
                    TenantProviderConfig.provider_id == Provider.id,
                    TenantProviderConfig.tenant_id == Agent.tenant_id
                )
            ).where(
                and_(
                    Agent.id == agent_id,
                    Agent.tenant_id == tenant_id,
                    Agent.is_enabled == True,
                    Provider.is_enabled == True,
                    ProviderModel.is_enabled == True,
                    TenantProviderConfig.is_enabled == True
                )
            )

            result = await self.db.execute(query)
            config_row = result.first()

            if config_row:
                agent, provider, provider_model, tenant_config = config_row

                api_keys = tenant_config.api_keys or []
                if not api_keys:
                    logger.warning(f"No API keys for tenant {tenant_id} and provider {provider.provider_name}")
                    return None

                # Safely handle None model_config and base_config
                model_config = provider_model.model_config or {}
                base_config = provider.base_config or {}
                
                llm_config = LLMProviderConfig(
                    name=provider.provider_name,
                    enabled=True,
                    models=[provider_model.model_name],
                    default_model=provider_model.model_name,
                    config={
                        **model_config,
                        "api_keys": api_keys,
                        "base_url": base_config.get("base_url"),
                        "timeout": base_config.get("timeout", 120),
                    }
                )

                # Initialize and return provider
                from services.llm.provider_manager import LLMProviderManager
                provider_class = LLMProviderManager.PROVIDER_CLASSES.get(provider.provider_name)
                if provider_class:
                    llm_provider = provider_class(llm_config)
                    success = await llm_provider.initialize()
                    if success:
                        logger.info(f"Initialized agent-specific LLM provider: {provider.provider_name}")
                        return llm_provider
                    else:
                        logger.warning(f"Failed to initialize agent-specific LLM provider: {provider.provider_name}")

            logger.debug(f"No agent-specific LLM config found for agent {agent_id}")
            return None

        except Exception as e:
            logger.error(f"Failed to get agent LLM provider for {agent_id}: {e}")
            return None

