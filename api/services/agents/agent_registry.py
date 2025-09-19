"""
Agent Registry Module
Manages agent definitions for departments
"""
from typing import Dict, Any
from utils.logging import get_logger

logger = get_logger(__name__)


class AgentRegistry:
    """Registry for managing agent definitions"""

    def __init__(self):
        self._agents: Dict[str, Dict[str, Any]] = {}
        self._initialized = False

    def register_agent(self, department_name: str, agent_info: Dict[str, Any]) -> None:
        """Register an agent definition for a department"""
        self._agents[department_name] = agent_info
        logger.info(f"Registered agent for department: {department_name}")

    def initialize(self) -> None:
        """Initialize the registry (no default agents)"""
        if self._initialized:
            return
        
        self._initialized = True
        logger.info("Agent registry initialized (no default agents)")

    def get_all_agents(self) -> Dict[str, Dict[str, Any]]:
        """Get all registered agents"""
        if not self._initialized:
            self.initialize()
        return self._agents.copy()
    
    def get_agent_for_department(self, department_name: str) -> Dict[str, Any]:
        """Get agent definition for specific department"""
        if not self._initialized:
            self.initialize()
        return self._agents.get(department_name, {})
    
    def has_agent_for_department(self, department_name: str) -> bool:
        """Check if agent is registered for department"""
        if not self._initialized:
            self.initialize()
        return department_name in self._agents


agent_registry = AgentRegistry()
