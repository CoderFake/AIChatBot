"""
Agent Service
Database-driven agent management service with department CRUD
Provide agents list to Reflection + Semantic Router for intelligent selection
"""

from typing import Dict, List, Optional, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from sqlalchemy.exc import SQLAlchemyError
from datetime import datetime
import json

from models.database.agent import Agent, AgentToolConfig
from models.database.tenant import Department, Tenant
from models.database.tool import Tool, TenantToolConfig
from utils.logging import get_logger
from utils.datetime_utils import DateTimeManager

from services.documents.document_service import DocumentService
from services.storage.minio_service import MinioService

logger = get_logger(__name__)


class AgentService:
    """Service for database-driven agent management with department CRUD"""
    
    def __init__(self, db_session: AsyncSession):
        self.db = db_session
        self._agent_cache: Dict[str, Dict[str, Any]] = {}
        self._cache_timestamp: Optional[datetime] = None
        self._cache_ttl = 300 
    
    def _is_cache_valid(self) -> bool:
        """Check if agent cache is still valid"""
        if not self._cache_timestamp:
            return False
        return (DateTimeManager._now() - self._cache_timestamp).seconds < self._cache_ttl
    
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
        logger.info("Agent cache invalidated")
    
    async def _get_agent_tools(self, agent_id: str) -> List[Dict[str, Any]]:
        """Get tools for specific agent"""
        try:
            result = await self.db.execute(
                select(AgentToolConfig)
                .join(Tool, AgentToolConfig.tool_id == Tool.id)
                .where(
                    and_(
                        AgentToolConfig.agent_id == str(agent_id),
                        AgentToolConfig.is_enabled == True,
                        Tool.is_enabled == True
                    )
                )
            )
            tool_configs = result.scalars().all()
            
            tools = []
            for config in tool_configs:
                if config.tool:
                    tools.append({
                        "id": str(config.tool.id),
                        "name": config.tool.tool_name,
                        "description": config.tool.description,
                        "config": config.tool_config or {}
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

    async def create_department_with_agent(
        self,
        tenant_id: str,
        department_name: str,
        agent_name: str,
        agent_description: str,
        provider_id: Optional[str] = None,
        model_id: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """Create department and its agent together (transactional + side-effects)"""
        try:
            result = await self.db.execute(
                select(Tenant).where(Tenant.id == tenant_id)
            )
            tenant = result.scalar_one_or_none()
            
            if not tenant:
                logger.error(f"Tenant {tenant_id} not found")
                return None
            
            department = Department(
                tenant_id=tenant_id,
                department_name=department_name
            )
            self.db.add(department)
            await self.db.flush()
            
            agent = Agent(
                agent_name=agent_name,
                description=agent_description,
                tenant_id=str(tenant.id),
                department_id=str(department.id),
                provider_id=provider_id,
                model_id=model_id,
                is_system=False,
                is_enabled=True
            )
            self.db.add(agent)
            await self.db.flush()

            doc_service = DocumentService(self.db)
            doc_meta = doc_service.create_department_root(
                tenant_id=str(tenant.id),
                department_id=str(department.id)
            )
            if not doc_meta or not doc_meta.get("document_root_id"):
                raise RuntimeError("Failed to initialize document root/collections")

            try:
                minio = MinioService()  
                bucket_path = f"{tenant.id}/{doc_meta['document_root_id']}"
                if hasattr(minio, 'ensure_bucket'):
                    minio.ensure_bucket(str(tenant.id))  
                if hasattr(minio, 'put_object'):
                    from io import BytesIO
                    empty = BytesIO(b"")
                    minio.put_object(str(tenant.id), f"{doc_meta['document_root_id']}/", empty, 0) 
            except Exception as storage_exc:
                logger.error(f"MinIO initialization failed: {storage_exc}")
                raise

            await self.db.commit()
            self.invalidate_cache()
            
            logger.info(f"Created department '{department_name}' with agent '{agent_name}' and initialized storage")
            
            return {
                "department": {
                    "id": str(department.id),
                    "name": department_name,
                    "tenant_id": tenant_id
                },
                "agent": {
                    "id": str(agent.id),
                    "name": agent_name,
                    "description": agent_description,
                    "tenant_id": str(tenant.id),
                    "department_id": str(department.id)
                },
                "document": doc_meta
            }
            
        except Exception as e:
            logger.error(f"Failed to create department with agent and storage init: {e}")
            await self.db.rollback()
            return None

    async def get_departments(self, tenant_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get departments list, optionally filtered by tenant"""
        try:
            query = select(Department)
            
            if tenant_id:
                query = query.where(Department.tenant_id == tenant_id)
            
            query = query.order_by(Department.department_name)
            
            result = await self.db.execute(query)
            departments = result.scalars().all()
            
            result_list = []
            for dept in departments:
                agent_result = await self.db.execute(
                    select(Agent).where(Agent.department_id == str(dept.id))
                )
                agents = agent_result.scalars().all()
                agent_count = len(agents)
                
                result_list.append({
                    "id": str(dept.id),
                    "name": dept.department_name,
                    "tenant_id": str(dept.tenant_id),
                    "tenant_name": dept.tenant.tenant_name if dept.tenant else None,
                    "agent_count": agent_count,
                    "created_at": dept.created_at.isoformat() if dept.created_at else None
                })
            
            return result_list
            
        except Exception as e:
            logger.error(f"Failed to get departments: {e}")
            return []

    async def get_department_by_id(self, department_id: str) -> Optional[Dict[str, Any]]:
        """Get department by ID with agent information"""
        try:
            result = await self.db.execute(
                select(Department).where(Department.id == department_id)
            )
            department = result.scalar_one_or_none()
            
            if not department:
                return None
            
            # Get agents for this department
            agent_result = await self.db.execute(
                select(Agent).where(Agent.department_id == department_id)
            )
            agents = agent_result.scalars().all()
            
            agents_data = []
            for agent in agents:
                agents_data.append({
                    "id": str(agent.id),
                    "name": agent.agent_name,
                    "description": agent.description,
                    "is_enabled": agent.is_enabled,
                    "is_system": agent.is_system
                })
            
            return {
                "id": str(department.id),
                "name": department.department_name,
                "tenant_id": str(department.tenant_id),
                "tenant_name": department.tenant.tenant_name if department.tenant else None,
                "agents": agents_data,
                "created_at": department.created_at.isoformat() if department.created_at else None
            }
            
        except Exception as e:
            logger.error(f"Failed to get department {department_id}: {e}")
            return None
    
    async def update_department(self, department_id: str, department_name: str) -> bool:
        """Update department name"""
        try:
            department = self.db.query(Department).filter(Department.id == department_id).first()
            
            if not department:
                return False
            
            department.department_name = department_name
            self.db.commit()
            
            # Invalidate cache as department name might be cached in agents
            self.invalidate_cache()
            
            logger.info(f"Updated department {department_id} name to '{department_name}'")
            return True
            
        except Exception as e:
            logger.error(f"Failed to update department {department_id}: {e}")
            self.db.rollback()
            return False
    
    async def delete_department(self, department_id: str, cascade: bool = True) -> bool:
        """Delete department and optionally its agents"""
        try:
            department = self.db.query(Department).filter(Department.id == department_id).first()
            
            if not department:
                return False
            
            if cascade:
                # Delete all agents in this department first
                agents = self.db.query(Agent).filter(Agent.department_id == department_id).all()
                for agent in agents:
                    # Delete agent tool configs
                    self.db.query(AgentToolConfig).filter(AgentToolConfig.agent_id == str(agent.id)).delete()
                    # Delete agent
                    self.db.delete(agent)
            else:
                # Check if department has agents
                agent_count = self.db.query(Agent).filter(Agent.department_id == department_id).count()
                if agent_count > 0:
                    logger.error(f"Cannot delete department {department_id}: has {agent_count} agents")
                    return False
            
            # Delete department
            self.db.delete(department)
            self.db.commit()
            
            # Invalidate cache
            self.invalidate_cache()
            
            logger.info(f"Deleted department {department_id} (cascade={cascade})")
            return True
            
        except Exception as e:
            logger.error(f"Failed to delete department {department_id}: {e}")
            self.db.rollback()
            return False
    
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
            # Check if department exists
            department = self.db.query(Department).filter(Department.id == department_id).first()
            if not department:
                logger.error(f"Department {department_id} not found")
                return None
            
            # Check if agent already exists for this department
            existing_agent = self.db.query(Agent).filter(Agent.department_id == department_id).first()
            if existing_agent:
                logger.warning(f"Agent already exists for department {department.department_name}")
                return existing_agent
            
            # Create agent
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
            self.db.commit()
            self.db.refresh(agent)
            
            # Invalidate cache
            self.invalidate_cache()
            
            logger.info(f"Created agent '{agent_name}' for department '{department.department_name}'")
            return agent
            
        except Exception as e:
            logger.error(f"Failed to create agent for department {department_id}: {e}")
            self.db.rollback()
            return None
    
    async def get_all_enabled_agents_raw(self) -> List[Agent]:
        """Get all enabled agents from database (raw ORM objects)"""
        try:
            result = await self.db.execute(
                select(Agent)
                .join(Department, Agent.department_id == Department.id)
                .where(Agent.is_enabled == True)
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
    
    async def get_agents_for_selection(self) -> List[Dict[str, str]]:
        """
        Get agents list for Reflection + Semantic Router selection
        Returns clean format with id, name, description for LLM processing
        """
        if not self._is_cache_valid():
            await self._refresh_cache()
        
        agents_for_selection = []
        
        for agent_id, agent_data in self._agent_cache.items():
            if agent_data.get("is_enabled"):
                agents_for_selection.append({
                    "id": agent_id,
                    "name": agent_data.get("name", ""),
                    "description": agent_data.get("description", "")
                })
        
        return agents_for_selection
    
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
    
    async def is_agent_enabled(self, agent_id: str) -> bool:
        """Check if agent is enabled"""
        agent = await self.get_agent_by_id(agent_id)
        return agent.get("is_enabled", False) if agent else False
    
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
            # Resolve tenant_id from department
            department = self.db.query(Department).filter(Department.id == department_id).first()
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
            self.db.commit()
            self.db.refresh(agent)
            
            self._cache_timestamp = None
            
            logger.info(f"Created agent: {agent_name} with ID: {agent.id}")
            return agent
            
        except Exception as e:
            logger.error(f"Failed to create agent {agent_name}: {e}")
            self.db.rollback()
            return None
    
    async def update_agent_status(self, agent_id: str, is_enabled: bool) -> bool:
        """Enable/disable agent"""
        try:
            agent = self.db.query(Agent).filter(Agent.id == agent_id).first()
            if not agent:
                return False
            
            agent.is_enabled = is_enabled
            self.db.commit()
            
            # Invalidate cache
            self._cache_timestamp = None
            
            logger.info(f"Updated agent {agent_id} status to {is_enabled}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to update agent {agent_id}: {e}")
            self.db.rollback()
            return False
    
    async def assign_tools_to_agent(self, agent_id: str, tool_ids: List[str]) -> bool:
        """Assign tools to agent with tenant-level policy enforcement"""
        try:
            agent = self.db.query(Agent).filter(Agent.id == agent_id).first()
            if not agent:
                return False
            
            # Enforce tenant-level allowed tools if available
            allowed_ids = await self._get_allowed_tool_ids_for_agent(agent)
            if allowed_ids is not None:
                disallowed = [tid for tid in tool_ids if tid not in allowed_ids]
                if disallowed:
                    logger.error(
                        f"Disallowed tools for agent {agent_id}: {disallowed}. Allowed set size={len(allowed_ids)}"
                    )
                    return False
            
            # Clear existing configs
            self.db.query(AgentToolConfig).filter(
                AgentToolConfig.agent_id == agent_id
            ).delete()
            
            # Assign new tools (ensure tool exists and enabled)
            for tool_id in tool_ids:
                tool = self.db.query(Tool).filter(
                    and_(Tool.id == tool_id, Tool.is_enabled == True)
                ).first()
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
            total_agents = self.db.query(Agent).count()
            enabled_agents = self.db.query(Agent).filter(Agent.is_enabled == True).count()
            
            dept_stats = {}
            departments = self.db.query(Department).all()
            for dept in departments:
                agent_count = (
                    self.db.query(Agent)
                    .filter(
                        and_(
                            Agent.department_id == dept.id,
                            Agent.is_enabled == True
                        )
                    )
                    .count()
                )
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
        api_keys: Optional[List[str]] = None,
        config_data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Create agent with provider configuration and encrypted API keys
        Called by DepartmentService - handles own errors and raises for rollback
        """
        try:
            # Import ProviderService here to avoid circular imports
            from services.providers.provider_service import ProviderService
            
            logger.info(f"Creating agent '{agent_name}' with provider '{provider_id}'")
            
            # Step 1: Validate department exists and belongs to tenant
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
            
            # Step 2: Create agent first
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
            await self.db.flush()  # Get agent ID
            logger.info(f"✓ Agent created: {agent.id}")
            
            # Step 3: Call ProviderService to handle provider config
            provider_service = ProviderService(self.db)
            provider_result = await provider_service.create_or_update_tenant_provider_config(
                tenant_id=tenant_id,
                provider_id=provider_id,
                api_keys=api_keys or [],
                config_data=config_data,
                rotation_strategy="round_robin"
            )
            logger.info(f"✓ Provider config handled: {provider_result['action']}")
            
            # Step 4: Invalidate cache
            from config.config_manager import config_manager
            await config_manager.invalidate_tenant_cache(tenant_id)
            self.invalidate_cache()
            
            # Return result
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
                },
                "provider_config": provider_result
            }
            
            logger.info(f"Created agent {agent_name} with provider config successfully")
            return result
            
        except ValueError as e:
            # Business logic errors - let them bubble up for transaction rollback
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
            # Import ProviderService here to avoid circular imports
            from services.providers.provider_service import ProviderService
            
            # Get agent
            result = await self.db.execute(
                select(Agent).where(Agent.id == agent_id)
            )
            agent = result.scalar_one_or_none()
            
            if not agent:
                logger.error(f"Agent {agent_id} not found")
                raise ValueError(f"Agent {agent_id} not found")
            
            # Update agent provider/model
            agent.provider_id = provider_id
            if model_id:
                agent.model_id = model_id
            
            await self.db.flush()
            
            # Call ProviderService to handle provider config
            provider_service = ProviderService(self.db)
            provider_result = await provider_service.create_or_update_tenant_provider_config(
                tenant_id=agent.tenant_id,
                provider_id=provider_id,
                api_keys=api_keys or [],
                config_data=config_data
            )
            
            # Invalidate cache
            from config.config_manager import config_manager
            await config_manager.invalidate_tenant_cache(agent.tenant_id)
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
        Rotate API key for agent and return new decrypted key
        """
        try:
            # Import ProviderService here to avoid circular imports
            from services.providers.provider_service import ProviderService
            
            # Get agent
            result = await self.db.execute(
                select(Agent).where(Agent.id == agent_id)
            )
            agent = result.scalar_one_or_none()
            
            if not agent or not agent.provider_id:
                logger.error(f"Agent {agent_id} not found or no provider configured")
                raise ValueError(f"Agent {agent_id} not found or no provider configured")
            
            # Call ProviderService to rotate key
            provider_service = ProviderService(self.db)
            rotation_result = await provider_service.rotate_api_key(
                tenant_id=agent.tenant_id,
                provider_id=agent.provider_id
            )
            
            # Invalidate cache
            from config.config_manager import config_manager
            await config_manager.invalidate_tenant_cache(agent.tenant_id)
            
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
        Get decrypted API key for agent - ready for API calls
        Only decrypt when actually needed for API calls
        """
        try:
            from config.config_manager import config_manager
            from utils.encryption_utils import encryption_service
            
            # Get agent
            result = await self.db.execute(
                select(Agent).where(Agent.id == agent_id)
            )
            agent = result.scalar_one_or_none()
            
            if not agent or not agent.provider_id:
                logger.warning(f"Agent {agent_id} not found or no provider configured")
                return None
            
            # Get cached provider configs for tenant
            tenant_providers = await config_manager.get_tenant_providers(agent.tenant_id)
            
            # Find provider config for this agent's department
            provider_key = f"{agent.provider_id}_{agent.department_id}"
            
            if provider_key in tenant_providers:
                provider_config = tenant_providers[provider_key]
                
                # Verify this config belongs to our agent
                if provider_config.get("agent_id") == str(agent.id):
                    encrypted_keys = provider_config.get("encrypted_api_keys", [])
                    current_key_index = provider_config.get("current_key_index", 0)
                    
                    if encrypted_keys and current_key_index < len(encrypted_keys):
                        # Decrypt current API key only when needed for API call
                        encrypted_current_key = encrypted_keys[current_key_index]
                        decrypted_key = encryption_service.decrypt(encrypted_current_key)
                        
                        logger.debug(f"Retrieved decrypted API key for agent {agent_id}")
                        return decrypted_key
                    else:
                        logger.warning(f"No valid API key at index {current_key_index} for agent {agent_id}")
                else:
                    logger.warning(f"Provider config agent mismatch for {agent_id}")
            else:
                logger.warning(f"No cached provider config found for agent {agent_id}")
            
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
            
            # Get provider info
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