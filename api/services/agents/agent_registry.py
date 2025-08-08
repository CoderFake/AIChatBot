"""
Agent Registry Module
Defines default agents for departments
"""
from typing import Dict, Any
from utils.logging import get_logger

logger = get_logger(__name__)


class AgentRegistry:
    """Registry holding default agent definitions"""

    def __init__(self):
        self._agents: Dict[str, Dict[str, Any]] = {}
        self._initialized = False

    def _register_default_agents(self) -> None:
        """Register built-in agents for common departments"""
        default_agents = {
            "hr": {
                "agent_name": "HR Assistant",
                "description": "Handles employee, policy and benefit queries",
                "capabilities": {"topics": ["employee", "policy", "benefits"]},
            },
            "finance": {
                "agent_name": "Finance Analyst",
                "description": "Manages budget, expense and revenue inquiries",
                "capabilities": {"topics": ["budget", "expense", "revenue"]},
            },
        }

        for dept, info in default_agents.items():
            self.register_agent(dept, info)

        logger.info("Registered %d default agents", len(default_agents))

    def register_agent(self, department_name: str, agent_info: Dict[str, Any]) -> None:
        """Register an agent definition for a department"""
        self._agents[department_name] = agent_info

    def initialize(self) -> None:
        if self._initialized:
            return
        try:
            self._register_default_agents()
            self._initialized = True
        except Exception as e:  # pragma: no cover - defensive
            logger.error("Failed to initialize agent registry: %s", e)
            raise

    def get_all_agents(self) -> Dict[str, Dict[str, Any]]:
        if not self._initialized:
            self.initialize()
        return self._agents.copy()


agent_registry = AgentRegistry()
