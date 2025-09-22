"""
Tool Manager Service
Manages tool instances, configurations, and execution
"""
import asyncio
from typing import Dict, Any, List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_
from models.database.tool import Tool
from models.database.agent import Agent, AgentToolConfig
from utils.logging import get_logger

logger = get_logger(__name__)


class ToolManager:
    """
    Centralized tool manager for handling tool instances and execution
    """

    def __init__(self, db: Optional[AsyncSession] = None):
        self.db = db
        self._tool_instances: Dict[str, Any] = {}
        self._tool_cache: Dict[str, Dict[str, Any]] = {}
        self._cache_timestamp = 0
        self._cache_ttl = 300  # 5 minutes
        self._initialized = False
        
    async def initialize(self):
        """Initialize tool manager with tool instances"""
        if self._initialized:
            return
            
        try:
            from tools.tool_registry import tool_registry
            await asyncio.get_event_loop().run_in_executor(None, tool_registry.initialize)
            
            tool_configs = tool_registry.get_all_tool_info()
            
            for tool_name, config in tool_configs.items():
                tool_instance = tool_registry.get_tool(tool_name)
                if tool_instance:
                    self._tool_instances[tool_name] = tool_instance
                    logger.debug(f"Loaded tool instance: {tool_name}")
            
            self._initialized = True
            logger.info(f"Tool manager initialized with {len(self._tool_instances)} tools")
            
        except Exception as e:
            logger.error(f"Failed to initialize tool manager: {e}")
            raise

    def _is_cache_valid(self) -> bool:
        """Check if tool cache is still valid"""
        import time
        return (time.time() - self._cache_timestamp) < self._cache_ttl

    async def _refresh_tool_cache(self):
        """Refresh tool cache from database"""
        if not self.db:
            return
            
        try:
            import time
            
            query = select(
                Tool.tool_name,
                Tool.description,
                Tool.category,
                Tool.base_config,
                AgentToolConfig.agent_id,
                AgentToolConfig.config_data,
                AgentToolConfig.usage_limits,
                AgentToolConfig.is_enabled.label("agent_tool_enabled"),
                Agent.tenant_id
            ).select_from(
                Tool
            ).join(
                AgentToolConfig, AgentToolConfig.tool_id == Tool.id
            ).join(
                Agent, Agent.id == AgentToolConfig.agent_id
            ).where(
                and_(
                    Tool.is_enabled,
                    Agent.is_enabled
                )
            )
            
            result = await self.db.execute(query)
            rows = result.fetchall()
            
            self._tool_cache.clear()
            
            for row in rows:
                tool_name = row.tool_name
                agent_id = str(row.agent_id)
                
                if tool_name not in self._tool_cache:
                    self._tool_cache[tool_name] = {
                        "description": row.description,
                        "category": row.category,
                        "base_config": row.base_config or {},
                        "agent_configs": {}
                    }
                
                self._tool_cache[tool_name]["agent_configs"][agent_id] = {
                    "config_data": row.config_data or {},
                    "usage_limits": row.usage_limits or {},
                    "is_enabled": row.agent_tool_enabled,
                    "tenant_id": str(row.tenant_id)
                }
            
            self._cache_timestamp = time.time()
            logger.debug(f"Refreshed tool cache with {len(self._tool_cache)} tools")
            
        except Exception as e:
            logger.error(f"Failed to refresh tool cache: {e}")

    async def get_tool_instance(self, tool_name: str, agent_id: str = None) -> Optional[Any]:
        """Get tool instance by name with optional agent-specific configuration"""
        try:
            if not self._initialized:
                await self.initialize()

            if not self._is_cache_valid():
                await self._refresh_tool_cache()

            tool_info = self._tool_cache.get(tool_name, {})
            agent_configs = tool_info.get("agent_configs", {})
            
            if agent_id:
                agent_config = agent_configs.get(agent_id)
                if not agent_config or not agent_config.get("is_enabled", False):
                    return None

            return self._tool_instances.get(tool_name)

        except Exception as e:
            logger.error(f"Failed to get tool instance: {e}")
            return None
    
    async def get_tool_config(self, tool_id: str, agent_id: str) -> Dict[str, Any]:
        """
        Get tool configuration for specific agent
        Merges base config with agent-specific config
        """
        try:
            if not self._is_cache_valid():
                await self._refresh_tool_cache()

            tool_info = self._tool_cache.get(tool_id, {})
            agent_configs = tool_info.get("agent_configs", {})
            agent_config = agent_configs.get(agent_id)

            if not agent_config:
                return {
                    "config": {},
                    "usage_limits": {},
                    "is_enabled": False
                }

            base_config = tool_info.get("base_config", {})
            agent_specific_config = agent_config.get("config_data", {})

            merged_config = {**base_config, **agent_specific_config}

            return {
                "config": merged_config,
                "usage_limits": agent_config.get("usage_limits", {}),
                "is_enabled": agent_config.get("is_enabled", False)
            }
        except Exception as e:
            logger.error(f"Failed to get tool config: {e}")
            return {
                "config": {},
                "usage_limits": {},
                "is_enabled": False
            }

    async def get_tools_for_user(
        self,
        user_id: str,
        agent_ids: List[str],
        tenant_id: str,
        user_access_levels: List[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Get available tools for a user based on their agents and access levels
        """
        try:
            if not self._is_cache_valid():
                await self._refresh_tool_cache()

            available_tools = []
            
            for tool_name, tool_info in self._tool_cache.items():
                agent_configs = tool_info.get("agent_configs", {})
                
                has_access = False
                for agent_id in agent_ids:
                    agent_config = agent_configs.get(agent_id)
                    if agent_config and agent_config.get("is_enabled", False):
                        if agent_config.get("tenant_id") == tenant_id:
                            has_access = True
                            break
                
                if has_access:
                    available_tools.append({
                        "tool_name": tool_name,
                        "description": tool_info.get("description", ""),
                        "category": tool_info.get("category", "general")
                    })
            
            logger.debug(f"Found {len(available_tools)} available tools for user {user_id}")
            return available_tools
            
        except Exception as e:
            logger.error(f"Failed to get tools for user: {e}")
            return []


    async def execute_tool(self, tool_name: str, params: Dict[str, Any], agent_providers: Dict[str, Any] = None, agent_id: str = None, user_context: Dict[str, Any] = None) -> Any:
        """
        Execute a tool with given parameters
        
        Args:
            tool_name: Name of the tool to execute
            params: Parameters for tool execution
            agent_providers: Dict of agent providers by agent_id
            agent_id: Agent ID to get specific provider for
            user_context: User context containing timezone and other info
            
        Returns:
            Tool execution result
        """
        try:
            if not self._initialized:
                await self.initialize()

            tool_instance = self._tool_instances.get(tool_name)
            if not tool_instance:
                raise ValueError(f"Tool {tool_name} not found or not initialized")

            if tool_name == "datetime" and user_context:
                tenant_timezone = user_context.get("timezone", "UTC")
                if "timezone" not in params or params.get("timezone") == "UTC":
                    params["timezone"] = tenant_timezone
                    logger.debug(f"Using tenant timezone for datetime tool: {tenant_timezone}")

            agent_provider_name = None
            if agent_providers and agent_id and agent_id in agent_providers:
                agent_provider_name = agent_providers[agent_id]
            elif agent_providers and not agent_id:
                if agent_providers:
                    agent_provider_name = next(iter(agent_providers.values()))

            execution_params = params.copy()
            
            if "query" in params:
                from services.tools.dynamic_tool_parser import DynamicToolParser
                
                parser = DynamicToolParser(self._tool_instances)
                if parser.should_parse_parameters(tool_name):
                    if not agent_provider_name:
                        raise ValueError(f"Agent provider name is required for {tool_name} tool parameter parsing")

                    query = params.get("query", "")
                    tenant_id = user_context.get("tenant_id") if user_context else None
                    parsed_params = await parser.parse_tool_parameters(
                        tool_name,
                        query,
                        agent_provider_name,
                        tenant_id,
                        user_context=user_context,
                    )
                    execution_params = parsed_params
            
            if hasattr(tool_instance, '_arun'):
                result = await tool_instance._arun(**execution_params)
            elif hasattr(tool_instance, 'arun'):
                result = await tool_instance.arun(**execution_params)
            elif hasattr(tool_instance, 'run'):
                result = tool_instance.run(**execution_params)
            else:
                raise ValueError(f"Tool {tool_name} does not have a valid execution method")

            return result

        except Exception as e:
            logger.error(f"Failed to execute tool {tool_name}: {e}")
            raise


tool_manager = ToolManager()