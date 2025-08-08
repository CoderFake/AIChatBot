import asyncio
import pytest

sqlalchemy = pytest.importorskip("sqlalchemy")
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select

from models.database.base import Base
from models.database.tenant import Tenant, Department
from models.database.agent import Agent
from services.agents.agent_sync_service import AgentSyncService


@pytest.mark.asyncio
async def test_agent_sync_creates_agent():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with AsyncSessionLocal() as session:
        tenant = Tenant(tenant_name="Acme")
        session.add(tenant)
        await session.flush()

        dept = Department(tenant_id=tenant.id, department_name="hr")
        session.add(dept)
        await session.commit()

        service = AgentSyncService(session)
        await service.initialize()

        result = await session.execute(select(Agent).where(Agent.department_id == dept.id))
        agent = result.scalar_one_or_none()
        assert agent is not None
        assert agent.agent_name == "HR Assistant"
