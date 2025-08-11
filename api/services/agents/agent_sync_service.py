"""
Agent synchronization service
Ensures default agents exist for registered departments
"""
from typing import Dict
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from models.database.agent import Agent
from models.database.tenant import Department
from utils.logging import get_logger
from .agent_registry import agent_registry

logger = get_logger(__name__)


class AgentSyncService:
    """Service to sync registry agents into database"""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def initialize(self) -> None:
        agent_registry.initialize()
        await self._sync_registry_to_database()

    async def _sync_registry_to_database(self) -> None:
        """Create or update agents for existing departments"""
        registry: Dict[str, Dict] = agent_registry.get_all_agents()
        if not registry:
            return

        # Load departments for names present in registry
        result = await self.db.execute(
            select(Department).where(Department.department_name.in_(registry.keys()))
        )
        departments = {dept.department_name: dept for dept in result.scalars().all()}

        agents_created = 0
        agents_updated = 0

        for dept_name, agent_info in registry.items():
            department = departments.get(dept_name)
            if not department:
                continue

            existing = await self.db.execute(
                select(Agent).where(Agent.department_id == department.id)
            )
            agent = existing.scalar_one_or_none()
            if agent is None:
                agent = Agent(
                    agent_name=agent_info["agent_name"],
                    description=agent_info["description"],
                    department_id=department.id,
                    capabilities=agent_info.get("capabilities", {}),
                    is_enabled=True,
                    is_system=True,
                )
                self.db.add(agent)
                agents_created += 1
                logger.info(
                    "Added default agent %s for department %s", agent.agent_name, dept_name
                )
            else:
                agent.agent_name = agent_info["agent_name"]
                agent.description = agent_info["description"]
                agent.capabilities = agent_info.get("capabilities", {})
                agent.is_system = True
                agents_updated += 1

        if agents_created or agents_updated:
            await self.db.commit()
            logger.info(
                "Agent registry sync completed - Added: %d, Updated: %d",
                agents_created,
                agents_updated,
            )
