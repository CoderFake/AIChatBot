"""
Tool Service - Database-First Tool Management
Sync từ tool_registry vào database và quản lý tools
"""
from typing import Dict, Any, List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from sqlalchemy.orm import selectinload

from models.database.tool import Tool
from models.database.agent import Agent, AgentTool
from services.tools.tool_registry import tool_registry
from utils.logging import get_logger

logger = get_logger(__name__)


class ToolService:
    """
    Database-First Tool Management Service
    - Seed tools từ tool_registry vào database
    - Mặc định tools TẮT để bảo mật
    """
    
    def __init__(self):
        self._initialized = False
    
    async def seed_tools_from_registry(self, db: AsyncSession) -> int:
        """
        Seed database từ tool_registry definitions
        Returns: số tools được tạo mới
        """
        try:
            all_tools = tool_registry.get_all_tools()
            created_count = 0
            
            for tool_name, tool_def in all_tools.items():
                # Kiểm tra tool đã tồn tại chưa
                existing_tool = await self.get_tool_by_name(db, tool_name)
                
                if not existing_tool:
                    # Tạo tool mới từ registry
                    new_tool = Tool(
                        name=tool_name,
                        display_name=tool_def.get("display_name", tool_name),
                        description=tool_def.get("description", ""),
                        category=tool_def.get("category", "utility_tools"),
                        is_enabled=False,  # MẶC ĐỊNH TẮT
                        tool_config=tool_def.get("tool_config", {})
                    )
                    
                    db.add(new_tool)
                    created_count += 1
                    logger.info(f"Seeded tool from registry: {tool_name}")
                else:
                    # Update tool definition nếu có thay đổi
                    updated = False
                    
                    if existing_tool.display_name != tool_def.get("display_name", tool_name):
                        existing_tool.display_name = tool_def.get("display_name", tool_name)
                        updated = True
                    
                    if existing_tool.description != tool_def.get("description", ""):
                        existing_tool.description = tool_def.get("description", "")
                        updated = True
                    
                    if existing_tool.category != tool_def.get("category", "utility_tools"):
                        existing_tool.category = tool_def.get("category", "utility_tools")
                        updated = True
                    
                    # Update tool_config nếu khác (merge)
                    registry_config = tool_def.get("tool_config", {})
                    if existing_tool.tool_config != registry_config:
                        existing_tool.tool_config = {**(existing_tool.tool_config or {}), **registry_config}
                        updated = True
                    
                    if updated:
                        logger.info(f"Updated tool from registry: {tool_name}")
            
            if created_count > 0:
                await db.commit()
                logger.info(f"Seeded {created_count} tools from registry")
            
            self._initialized = True
            return created_count
            
        except Exception as e:
            logger.error(f"Failed to seed tools from registry: {e}")
            await db.rollback()
            return 0
    
    async def get_all_tools(self, db: AsyncSession) -> List[Tool]:
        """Lấy tất cả tools từ database"""
        try:
            result = await db.execute(
                select(Tool).order_by(Tool.category, Tool.name)
            )
            return result.scalars().all()
        except Exception as e:
            logger.error(f"Failed to get all tools: {e}")
            return []
    
    async def get_enabled_tools(self, db: AsyncSession) -> List[Tool]:
        """Lấy tools đang enabled"""
        try:
            result = await db.execute(
                select(Tool).where(Tool.is_enabled == True).order_by(Tool.name)
            )
            return result.scalars().all()
        except Exception as e:
            logger.error(f"Failed to get enabled tools: {e}")
            return []
    
    async def get_tool_by_name(self, db: AsyncSession, tool_name: str) -> Optional[Tool]:
        """Lấy tool theo tên"""
        try:
            result = await db.execute(
                select(Tool).where(Tool.name == tool_name)
            )
            return result.scalars().first()
        except Exception as e:
            logger.error(f"Failed to get tool {tool_name}: {e}")
            return None
    
    async def get_tools_by_category(self, db: AsyncSession, category: str) -> List[Tool]:
        """Lấy tools theo category"""
        try:
            result = await db.execute(
                select(Tool).where(
                    and_(
                        Tool.category == category,
                        Tool.is_enabled == True
                    )
                )
            )
            return result.scalars().all()
        except Exception as e:
            logger.error(f"Failed to get tools for category {category}: {e}")
            return []
    
    async def toggle_tool(self, db: AsyncSession, tool_name: str, enabled: bool) -> bool:
        """Bật/tắt tool"""
        try:
            tool = await self.get_tool_by_name(db, tool_name)
            if not tool:
                logger.warning(f"Tool {tool_name} not found in database")
                return False
            
            old_status = tool.is_enabled
            tool.is_enabled = enabled
            await db.commit()
            
            logger.info(f"Tool {tool_name}: {old_status} -> {enabled}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to toggle tool {tool_name}: {e}")
            await db.rollback()
            return False
    
    async def update_tool_config(
        self, 
        db: AsyncSession, 
        tool_name: str, 
        config: Dict[str, Any]
    ) -> bool:
        """Cập nhật config của tool"""
        try:
            tool = await self.get_tool_by_name(db, tool_name)
            if not tool:
                return False
            
            # Merge config
            current_config = tool.tool_config or {}
            tool.tool_config = {**current_config, **config}
            
            await db.commit()
            logger.info(f"Updated config for tool {tool_name}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to update tool config {tool_name}: {e}")
            await db.rollback()
            return False
    
    async def assign_tool_to_agent(
        self, 
        db: AsyncSession, 
        agent_name: str, 
        tool_name: str,
        enabled: bool = True
    ) -> bool:
        """Assign tool cho agent"""
        try:
            # Get agent
            agent_result = await db.execute(
                select(Agent).where(Agent.name == agent_name)
            )
            agent = agent_result.scalars().first()
            if not agent:
                logger.warning(f"Agent {agent_name} not found")
                return False
            
            # Get tool  
            tool = await self.get_tool_by_name(db, tool_name)
            if not tool:
                logger.warning(f"Tool {tool_name} not found")
                return False
            
            # Check existing relationship
            existing_result = await db.execute(
                select(AgentTool).where(
                    and_(
                        AgentTool.agent_id == agent.id,
                        AgentTool.tool_id == tool.id
                    )
                )
            )
            existing = existing_result.scalars().first()
            
            if existing:
                # Update existing
                existing.is_enabled = enabled
                logger.info(f"Updated agent-tool: {agent_name} - {tool_name} -> {enabled}")
            else:
                # Create new relationship
                agent_tool = AgentTool(
                    agent_id=agent.id,
                    tool_id=tool.id,
                    is_enabled=enabled
                )
                db.add(agent_tool)
                logger.info(f"Assigned tool to agent: {agent_name} - {tool_name}")
            
            await db.commit()
            return True
            
        except Exception as e:
            logger.error(f"Failed to assign tool {tool_name} to agent {agent_name}: {e}")
            await db.rollback()
            return False
    
    async def get_agent_tools(self, db: AsyncSession, agent_name: str) -> List[Dict[str, Any]]:
        """Lấy tools của agent"""
        try:
            result = await db.execute(
                select(Agent).options(
                    selectinload(Agent.agent_tools).selectinload(AgentTool.tool)
                ).where(Agent.name == agent_name)
            )
            agent = result.scalars().first()
            
            if not agent:
                return []
            
            tools = []
            for agent_tool in agent.agent_tools:
                tools.append({
                    "name": agent_tool.tool.name,
                    "display_name": agent_tool.tool.display_name,
                    "category": agent_tool.tool.category,
                    "description": agent_tool.tool.description,
                    "enabled": agent_tool.is_enabled,
                    "tool_enabled": agent_tool.tool.is_enabled,
                    "tool_config": agent_tool.tool.tool_config
                })
            
            return tools
            
        except Exception as e:
            logger.error(f"Failed to get tools for agent {agent_name}: {e}")
            return []
    
    async def sync_with_registry(self, db: AsyncSession) -> Dict[str, int]:
        """
        Sync database với tool_registry (cập nhật definitions)
        Returns: thống kê sync
        """
        try:
            stats = {"updated": 0, "created": 0, "errors": 0}
            
            # Seed new tools
            created = await self.seed_tools_from_registry(db)
            stats["created"] = created
            
            logger.info(f"Registry sync completed: {stats}")
            return stats
            
        except Exception as e:
            logger.error(f"Failed to sync with registry: {e}")
            return {"updated": 0, "created": 0, "errors": 1}


# Singleton instance
tool_service = ToolService() 