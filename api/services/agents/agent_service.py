"""
Agent Service
Database-driven agent management service
Provide agents list to Reflection + Semantic Router for intelligent selection
"""

from typing import Dict, List, Optional, Any
from sqlalchemy.orm import Session
from sqlalchemy import and_
from datetime import datetime
import json

from models.database.agent import Agent, AgentToolConfig
from models.database.tenant import Department  
from models.database.tool import Tool
from utils.logging import get_logger

logger = get_logger(__name__)


class AgentService:
    """Service for database-driven agent management"""
    
    def __init__(self, db_session: Session):
        self.db = db_session
        self._agent_cache: Dict[str, Dict[str, Any]] = {}
        self._cache_timestamp: Optional[datetime] = None
        self._cache_ttl = 300 
    
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
    
    def _get_agent_tools(self, agent_id: str) -> List[Dict[str, Any]]:
        """Get tools available for specific agent"""
        try:
            tool_configs = (
                self.db.query(AgentToolConfig)
                .join(Tool)
                .filter(
                    and_(
                        AgentToolConfig.agent_id == agent_id,
                        AgentToolConfig.is_enabled == True,
                        Tool.is_enabled == True
                    )
                )
                .all()
            )
            
            tools = []
            for config in tool_configs:
                if config.tool:
                    tools.append({
                        "tool_id": str(config.tool.id),
                        "tool_name": config.tool.tool_name,
                        "category": config.tool.category,
                        "config_data": config.config_data or {}
                    })
            
            return tools
            
        except Exception as e:
            logger.error(f"Failed to get tools for agent {agent_id}: {e}")
            return []
    
    def _get_agent_extended_config(self, agent_id: str) -> Dict[str, Any]:
        """Get extended configuration from agent_tool_configs.config_data"""
        try:
            config_data = {}
            
            tool_configs = (
                self.db.query(AgentToolConfig)
                .filter(AgentToolConfig.agent_id == agent_id)
                .all()
            )
            
            for config in tool_configs:
                if config.config_data:
                    if isinstance(config.config_data, dict):
                        config_data.update(config.config_data)
                    elif isinstance(config.config_data, str):
                        try:
                            parsed_config = json.loads(config.config_data)
                            config_data.update(parsed_config)
                        except json.JSONDecodeError:
                            pass
            
            return config_data
            
        except Exception as e:
            logger.error(f"Failed to get extended config for agent {agent_id}: {e}")
            return {}
    
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
            agent = Agent(
                agent_name=agent_name,
                description=description,
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
        """Assign tools to agent"""
        try:
            agent = self.db.query(Agent).filter(Agent.id == agent_id).first()
            if not agent:
                return False
            
            self.db.query(AgentToolConfig).filter(
                AgentToolConfig.agent_id == agent_id
            ).delete()
            
            for tool_id in tool_ids:
                tool = self.db.query(Tool).filter(Tool.id == tool_id).first()
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
    
    def invalidate_cache(self) -> None:
        """Force cache refresh on next request"""
        self._cache_timestamp = None
        logger.info("Agent cache invalidated")
    
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