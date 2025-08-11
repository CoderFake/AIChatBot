"""
Agent Service
Database-driven agent management service with department CRUD
Provide agents list to Reflection + Semantic Router for intelligent selection
"""

from typing import Dict, List, Optional, Any
from sqlalchemy.orm import Session
from sqlalchemy import and_
from datetime import datetime
import json

from models.database.agent import Agent, AgentToolConfig
from models.database.tenant import Department, Tenant
from models.database.tool import Tool, TenantToolConfig
from utils.logging import get_logger

# New services
from services.documents.document_service import DocumentService
from services.storage.minio_service import MinioService

logger = get_logger(__name__)


class AgentService:
    """Service for database-driven agent management with department CRUD"""
    
    def __init__(self, db_session: Session):
        self.db = db_session
        self._agent_cache: Dict[str, Dict[str, Any]] = {}
        self._cache_timestamp: Optional[datetime] = None
        self._cache_ttl = 300 
    
    # Cache management methods
    def _is_cache_valid(self) -> bool:
        """Check if agent cache is still valid"""
        if not self._cache_timestamp:
            return False
        return (datetime.now() - self._cache_timestamp).seconds < self._cache_ttl
    
    def _refresh_cache(self) -> None:
        """Refresh agent cache from database"""
        try:
            agents = self.get_all_enabled_agents_raw()
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
                    "tools": self._get_agent_tools(agent.id),
                    "config_data": self._get_agent_extended_config(agent.id)
                }
            
            self._cache_timestamp = datetime.now()
            logger.info(f"Agent cache refreshed with {len(self._agent_cache)} agents")
            
        except Exception as e:
            logger.error(f"Failed to refresh agent cache: {e}")
            if not self._agent_cache:
                self._agent_cache = {}
    
    def invalidate_cache(self) -> None:
        """Force cache refresh on next request"""
        self._cache_timestamp = None
        logger.info("Agent cache invalidated")
    
    # Department CRUD methods
    def create_department_with_agent(
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
            tenant = self.db.query(Tenant).filter(Tenant.id == tenant_id).first()
            if not tenant:
                logger.error(f"Tenant {tenant_id} not found")
                return None
            
            # Begin transactional creation
            department = Department(
                tenant_id=tenant_id,
                department_name=department_name
            )
            self.db.add(department)
            self.db.flush()
            
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
            self.db.flush()

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

            self.db.commit()
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
            self.db.rollback()
            return None
    
    def get_departments(self, tenant_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get departments list, optionally filtered by tenant"""
        try:
            query = self.db.query(Department)
            
            if tenant_id:
                query = query.filter(Department.tenant_id == tenant_id)
            
            departments = query.order_by(Department.department_name).all()
            
            result = []
            for dept in departments:
                agent_count = (
                    self.db.query(Agent)
                    .filter(Agent.department_id == str(dept.id))
                    .count()
                )
                
                result.append({
                    "id": str(dept.id),
                    "name": dept.department_name,
                    "tenant_id": str(dept.tenant_id),
                    "tenant_name": dept.tenant.tenant_name if dept.tenant else None,
                    "agent_count": agent_count,
                    "created_at": dept.created_at.isoformat() if dept.created_at else None
                })
            
            return result
            
        except Exception as e:
            logger.error(f"Failed to get departments: {e}")
            return []
    
    def get_department_by_id(self, department_id: str) -> Optional[Dict[str, Any]]:
        """Get department by ID with agent information"""
        try:
            department = self.db.query(Department).filter(Department.id == department_id).first()
            
            if not department:
                return None
            
            # Get agents for this department
            agents = (
                self.db.query(Agent)
                .filter(Agent.department_id == department_id)
                .all()
            )
            
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
    
    def update_department(self, department_id: str, department_name: str) -> bool:
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
    
    def delete_department(self, department_id: str, cascade: bool = True) -> bool:
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
    
    def create_agent_for_existing_department(
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
    
    def get_all_enabled_agents_raw(self) -> List[Agent]:
        """Get all enabled agents from database (raw ORM objects)"""
        try:
            return (
                self.db.query(Agent)
                .join(Department, Agent.department_id == Department.id)
                .filter(Agent.is_enabled == True)
                .order_by(Agent.agent_name)
                .all()
            )
        except Exception as e:
            logger.error(f"Failed to get enabled agents: {e}")
            return []
    
    def get_all_enabled_agents(self) -> Dict[str, Dict[str, Any]]:
        """Get all enabled agents formatted for orchestrator"""
        if not self._is_cache_valid():
            self._refresh_cache()
        
        return self._agent_cache.copy()
    
    def get_agents_for_selection(self) -> List[Dict[str, str]]:
        """
        Get agents list for Reflection + Semantic Router selection
        Returns clean format with id, name, description for LLM processing
        """
        if not self._is_cache_valid():
            self._refresh_cache()
        
        agents_for_selection = []
        
        for agent_id, agent_data in self._agent_cache.items():
            if agent_data.get("is_enabled"):
                agents_for_selection.append({
                    "id": agent_id,
                    "name": agent_data.get("name", ""),
                    "description": agent_data.get("description", "")
                })
        
        return agents_for_selection
    
    def get_agent_by_id(self, agent_id: str) -> Optional[Dict[str, Any]]:
        """Get specific agent by ID"""
        if not self._is_cache_valid():
            self._refresh_cache()
        
        return self._agent_cache.get(agent_id)
    
    def get_agents_by_department(self, department_id: str) -> Dict[str, Dict[str, Any]]:
        """Get agents by department ID"""
        if not self._is_cache_valid():
            self._refresh_cache()
        
        return {
            agent_id: agent for agent_id, agent in self._agent_cache.items()
            if agent.get("department_id") == department_id
        }
    
    def get_agent_tools(self, agent_id: str) -> List[Dict[str, Any]]:
        """Get tools available for specific agent"""
        agent = self.get_agent_by_id(agent_id)
        return agent.get("tools", []) if agent else []
    
    def _get_allowed_tool_ids_for_agent(self, agent: Agent) -> Optional[set]:
        """Resolve allowed tool IDs from tenant policy (tenant_tool_configs). Return None if not enforceable."""
        try:
            # Load department to get tenant_id
            department = self.db.query(Department).filter(Department.id == agent.department_id).first()
            if not department:
                return None
            tenant_id = department.tenant_id
            if not tenant_id:
                return None
            # Fetch allowed tool ids for tenant
            configs = (
                self.db.query(TenantToolConfig)
                .filter(
                    and_(
                        TenantToolConfig.tenant_id == tenant_id,
                        TenantToolConfig.is_enabled == True,
                    )
                )
                .all()
            )
            return {str(cfg.tool_id) for cfg in configs}
        except Exception as e:
            # If model/table not present or any failure, do not block flow
            logger.warning(f"Skip tenant allowed tools enforcement due to error: {e}")
            return None
    
    def is_agent_enabled(self, agent_id: str) -> bool:
        """Check if agent is enabled"""
        agent = self.get_agent_by_id(agent_id)
        return agent.get("is_enabled", False) if agent else False
    
    def get_agent_config(self, agent_id: str) -> Dict[str, Any]:
        """Get complete agent configuration from database"""
        agent = self.get_agent_by_id(agent_id)
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
    
    def create_agent(
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
    
    def update_agent_status(self, agent_id: str, is_enabled: bool) -> bool:
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
    
    def assign_tools_to_agent(self, agent_id: str, tool_ids: List[str]) -> bool:
        """Assign tools to agent with tenant-level policy enforcement"""
        try:
            agent = self.db.query(Agent).filter(Agent.id == agent_id).first()
            if not agent:
                return False
            
            # Enforce tenant-level allowed tools if available
            allowed_ids = self._get_allowed_tool_ids_for_agent(agent)
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
    
    def get_stats(self) -> Dict[str, Any]:
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