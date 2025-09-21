"""
Base Agent Class for Multi-Agent RAG System
Provides common functionality for all domain agents
"""
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
from datetime import datetime
import asyncio
import json

from langchain_core.runnables import RunnableConfig
from langchain_core.messages import BaseMessage

from services.tools.tool_manager import tool_manager
from services.auth.permission_service import PermissionService
from config.database import get_db_context
from utils.logging import get_logger

logger = get_logger(__name__)


class BaseAgent(ABC):
    """
    Base agent class with common functionality for all domain agents
    """

    def __init__(self, agent_data: Dict[str, Any]):
        """
        Initialize agent from database data
        """
        self.agent_id = str(agent_data.get("id", ""))
        self.agent_name = agent_data.get("name", "")
        self.description = agent_data.get("description", "")
        self.tenant_id = agent_data.get("tenant_id")
        self.department_id = agent_data.get("department_id")
        self.department_name = agent_data.get("department_name")
        self.provider_id = agent_data.get("provider_id")
        self.provider_name = agent_data.get("provider_name")
        self.model_id = agent_data.get("model_id")
        self.model_name = agent_data.get("model_name")
        self.is_enabled = agent_data.get("is_enabled", True)
        self.is_system = agent_data.get("is_system", False)

        self.tools = []
        self.provider_config = {}
        self.created_at = datetime.now()
        self.last_execution = None

    async def initialize_from_db(self) -> None:
        """Initialize agent configuration from database"""
        try:
            async with get_db_context() as db:
                from services.agents.agent_service import AgentService
                agent_service = AgentService(db)

                agent_config = await agent_service.get_agent_config(self.agent_id)
                self.provider_config = agent_config

                agent_tools = await agent_service.get_agent_tools(self.agent_id)
                self.tools = agent_tools

                logger.info(f"Initialized agent {self.agent_name} with {len(self.tools)} tools")

        except Exception as e:
            logger.error(f"Failed to initialize agent {self.agent_name}: {e}")
            raise

    async def execute_with_tools(
        self,
        query: str,
        user_context: Dict[str, Any],
        config: RunnableConfig
    ) -> Dict[str, Any]:
        """
        Execute agent with tool support
        """
        start_time = datetime.now()
        tool_results = {}
        sources = []

        try:
            for tool_info in self.tools:
                tool_id = tool_info.get("id")
                tool_name = tool_info.get("name")

                if await self._can_use_tool(tool_id, user_context):
                    try:
                        tool_result = await tool_manager.execute_tool(
                            tool_id, tool_name, query, user_context, self.provider_config
                        )
                        tool_results[tool_name] = tool_result

                        if tool_name == "rag_tool" and "sources" in tool_result:
                            sources.extend(tool_result["sources"])

                        logger.info(f"Tool {tool_name} executed successfully for agent {self.agent_name}")

                    except Exception as e:
                        logger.warning(f"Tool {tool_name} failed for agent {self.agent_name}: {e}")
                        tool_results[tool_name] = {"error": str(e)}

            response_content = await self._generate_response(query, tool_results, user_context)

            execution_time = (datetime.now() - start_time).total_seconds()

            return {
                "agent_id": self.agent_id,
                "agent_name": self.agent_name,
                "content": response_content,
                "confidence": self._calculate_confidence(tool_results),
                "tools_used": list(tool_results.keys()),
                "sources": sources,
                "execution_time": execution_time,
                "status": "completed"
            }

        except Exception as e:
            execution_time = (datetime.now() - start_time).total_seconds()
            logger.error(f"Agent {self.agent_name} execution failed: {e}")

            return {
                "agent_id": self.agent_id,
                "agent_name": self.agent_name,
                "content": f"Error: {str(e)}",
                "confidence": 0.0,
                "tools_used": [],
                "sources": [],
                "execution_time": execution_time,
                "status": "failed",
                "error": str(e)
            }

    async def _can_use_tool(self, tool_id: str, user_context: Dict[str, Any]) -> bool:
        """Check if user has permission to use tool"""
        try:
            async with get_db_context() as db:
                permission_service = PermissionService(db)
                return True
        except Exception:
            return False

    def _calculate_confidence(self, tool_results: Dict[str, Any]) -> float:
        """Calculate confidence score based on tool results"""
        if not tool_results:
            return 0.5

        successful_tools = sum(1 for result in tool_results.values()
                             if isinstance(result, dict) and "error" not in result)

        if successful_tools == 0:
            return 0.2

        confidence = min(0.9, successful_tools / len(tool_results))
        return round(confidence, 2)

    @abstractmethod
    async def _generate_response(
        self,
        query: str,
        tool_results: Dict[str, Any],
        user_context: Dict[str, Any]
    ) -> str:
        """
        Generate agent-specific response using tool results
        Must be implemented by each domain agent
        """
        pass

    def get_agent_info(self) -> Dict[str, Any]:
        """Get agent information for debugging/logging"""
        return {
            "agent_id": self.agent_id,
            "agent_name": self.agent_name,
            "description": self.description,
            "department": self.department_name,
            "tools_count": len(self.tools),
            "provider": self.provider_name,
            "model": self.model_name,
            "is_enabled": self.is_enabled,
            "is_system": self.is_system,
            "created_at": self.created_at.isoformat(),
            "last_execution": self.last_execution.isoformat() if self.last_execution else None
        }

    def update_last_execution(self):
        """Update last execution timestamp"""
        self.last_execution = datetime.now()

    async def health_check(self) -> bool:
        """Check if agent is healthy and ready"""
        try:
            if not self.provider_config:
                return False

            return True

        except Exception as e:
            logger.error(f"Health check failed for agent {self.agent_name}: {e}")
            return False


class AgentFactory:
    """
    Factory class to create agents from database data
    """

    @staticmethod
    def create_agent(agent_data: Dict[str, Any]) -> Optional[BaseAgent]:
        """
        Create appropriate agent instance based on agent data from database
        For now, all agents use the same base functionality
        """
        agent_name = agent_data.get("name", "").lower()

        return GenericAgent(agent_data)

    @staticmethod
    async def create_single_agent(agent_id: str) -> Optional[BaseAgent]:
        """
        Create single agent instance from database by ID
        """
        try:
            async with get_db_context() as db:
                from services.agents.agent_service import AgentService
                agent_service = AgentService(db)

                agent_data = await agent_service.get_agent_by_id(agent_id)
                if not agent_data:
                    logger.warning(f"Agent {agent_id} not found in database")
                    return None

                agent = AgentFactory.create_agent(agent_data)
                if agent:
                    await agent.initialize_from_db()
                    logger.info(f"Created agent {agent.agent_name} from database")
                    return agent

                return None

        except Exception as e:
            logger.error(f"Failed to create single agent {agent_id}: {e}")
            return None

    @staticmethod
    async def create_agents_from_db(tenant_id: str) -> Dict[str, BaseAgent]:
        """
        Create all enabled agents for a tenant from database
        """
        try:
            async with get_db_context() as db:
                from services.agents.agent_service import AgentService
                agent_service = AgentService(db)

                agents_data = await agent_service.get_all_enabled_agents()

                agents = {}
                for agent_id, agent_data in agents_data.items():
                    if agent_data.get("tenant_id") == tenant_id:
                        agent = AgentFactory.create_agent(agent_data)
                        if agent:
                            await agent.initialize_from_db()
                            agents[agent_id] = agent

                logger.info(f"Created {len(agents)} agents for tenant {tenant_id}")
                return agents

        except Exception as e:
            logger.error(f"Failed to create agents from database: {e}")
            return {}


class GenericAgent(BaseAgent):
    """
    Generic agent for departments that don't have specialized implementations yet
    Uses the same base functionality but can be extended later
    """

    pass