from typing import Dict, Any, List, Optional, Callable
import asyncio
import json
from utils.datetime_utils import CustomDateTime as datetime

from config.settings import get_settings, reload_settings, Settings
from services.llm.provider_manager import llm_provider_manager
from services.tools.tool_manager import tool_manager
from utils.logging import get_logger
from common.types import ConfigChangeType
from common.dataclasses import ConfigChange

logger = get_logger(__name__)


class ConfigSubscriber:
    """Base class for configuration subscribers"""
    
    async def on_config_change(self, change: ConfigChange) -> bool:
        """Handle configuration change"""
        return True

class ConfigManager:

    def __init__(self):
        self._subscribers: Dict[str, List[ConfigSubscriber]] = {}
        self._current_settings: Optional[Settings] = None
        self._monitoring = False
        self._change_queue: asyncio.Queue = asyncio.Queue()
        
    async def initialize(self):
        """Initialize configuration manager và tất cả components"""
        try:
            self._current_settings = get_settings()
            
            if not llm_provider_manager._initialized:
                await llm_provider_manager.initialize()
                logger.info("LLM Provider Manager initialized")
            
            if not hasattr(tool_manager, '_initialized') or not tool_manager._initialized:
                tool_manager.reload_tools()
                logger.info("Tool Manager initialized")
            
            if not self._monitoring:
                asyncio.create_task(self._monitor_changes())
            
            logger.info("Configuration manager initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize config manager: {e}")
            raise
    
    async def reinitialize(self):
        """Reinitialize configuration manager với settings mới"""
        try:
            logger.info("Reinitializing configuration manager...")
            
            self._current_settings = reload_settings()
            
            if llm_provider_manager._initialized:
                llm_provider_manager._initialized = False
            await llm_provider_manager.initialize()
            logger.info("LLM Provider Manager reinitialized")
            
            tool_manager.reload_tools()
            logger.info("Tool Manager reinitialized")
            
            logger.info("Configuration manager reinitialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to reinitialize config manager: {e}")
            raise
    
    def subscribe(self, component_name: str, subscriber: ConfigSubscriber):
        """Subscribe to configuration changes"""
        if component_name not in self._subscribers:
            self._subscribers[component_name] = []
        
        self._subscribers[component_name].append(subscriber)
        logger.info(f"Component {component_name} subscribed to config changes")
    
    def unsubscribe(self, component_name: str, subscriber: ConfigSubscriber):
        """Unsubscribe from configuration changes"""
        if component_name in self._subscribers:
            self._subscribers[component_name].remove(subscriber)
    
    async def apply_config_change(self, change_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Apply configuration change từ API requests
        Returns status of the change application
        """
        try:
            change_type = change_data.get("change_type")
            component_name = change_data.get("component_name")
            new_config = change_data.get("config")
            
            logger.info(f"Applying config change: {change_type} for {component_name}")
            
            config_change = await self._create_config_change(
                change_type, component_name, new_config
            )
            
            if not config_change:
                return {"success": False, "error": "Invalid change data"}
            
            success = await self._apply_immediate_change(config_change)
            
            if success:
                await self._change_queue.put(config_change)
                
                return {
                    "success": True,
                    "change_id": f"{component_name}_{datetime.now().timestamp()}",
                    "message": f"Configuration change applied for {component_name}"
                }
            else:
                return {"success": False, "error": f"Failed to apply change for {component_name}"}
            
        except Exception as e:
            logger.error(f"Failed to apply config change: {e}")
            return {"success": False, "error": str(e)}
    
    async def _apply_immediate_change(self, change: ConfigChange) -> bool:
        """Apply change immediately để có real-time response"""
        try:
            setting_success = await self._apply_setting_change(change)
            
            if not setting_success:
                return False
            
            component_success = await self._apply_component_change(change)
            
            return component_success
            
        except Exception as e:
            logger.error(f"Failed to apply immediate change: {e}")
            return False
    
    async def _apply_component_change(self, change: ConfigChange) -> bool:
        try:
            if change.change_type.name.startswith("PROVIDER_"):
                return await self._apply_provider_change(change)
            elif change.change_type.name.startswith("TOOL_"):
                return await self._apply_tool_change(change)
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to apply component change: {e}")
            return False
    
    async def _apply_provider_change(self, change: ConfigChange) -> bool:
        """Apply provider configuration change"""
        try:
            provider_name = change.component_name
            
            if change.change_type == ConfigChangeType.PROVIDER_ENABLED:
                if provider_name in llm_provider_manager._providers:
                    logger.info(f"Provider {provider_name} already initialized and enabled")
                else:
                    await self._reinitialize_provider_manager()
                    
            elif change.change_type == ConfigChangeType.PROVIDER_DISABLED:
                if provider_name in llm_provider_manager._providers:
                    del llm_provider_manager._providers[provider_name]
                    logger.info(f"Provider {provider_name} disabled and removed")
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to apply provider change: {e}")
            return False
    
    async def _apply_tool_change(self, change: ConfigChange) -> bool:
        """Apply tool configuration change"""
        try:
            tool_name = change.component_name
            
            if change.change_type == ConfigChangeType.TOOL_ENABLED:
                tool_manager.reload_tools()
                logger.info(f"Tool {tool_name} enabled - tools reloaded")
                
            elif change.change_type == ConfigChangeType.TOOL_DISABLED:
                tool_manager.reload_tools()
                logger.info(f"Tool {tool_name} disabled - tools reloaded")
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to apply tool change: {e}")
            return False
    
    async def _reinitialize_provider_manager(self):
        """Reinitialize provider manager"""
        try:
            llm_provider_manager._initialized = False
            await llm_provider_manager.initialize()
            logger.info("Provider manager reinitialized")
        except Exception as e:
            logger.error(f"Failed to reinitialize provider manager: {e}")
            raise
    
    async def _create_config_change(
        self, 
        change_type: str, 
        component_name: str, 
        new_config: Any
    ) -> Optional[ConfigChange]:
        """Create ConfigChange object from admin input"""
        
        try:
            change_enum = ConfigChangeType(change_type)
            
            old_value = None
            if change_enum in [ConfigChangeType.PROVIDER_ENABLED, ConfigChangeType.PROVIDER_DISABLED]:
                if hasattr(self._current_settings, 'llm_providers') and self._current_settings.llm_providers:
                    provider_config = self._current_settings.llm_providers.get(component_name)
                    old_value = provider_config.enabled if provider_config else False
            elif change_enum in [ConfigChangeType.TOOL_ENABLED, ConfigChangeType.TOOL_DISABLED]:
                if hasattr(self._current_settings, 'tools') and self._current_settings.tools:
                    old_value = self._current_settings.tools.get(component_name, {}).get("enabled", False)
            elif change_enum in [ConfigChangeType.AGENT_ENABLED, ConfigChangeType.AGENT_DISABLED]:
                if hasattr(self._current_settings, 'agents') and self._current_settings.agents:
                    agent_config = self._current_settings.agents.get(component_name)
                    old_value = agent_config.enabled if agent_config else False
            
            return ConfigChange(
                change_type=change_enum,
                component_name=component_name,
                old_value=old_value,
                new_value=new_config,
                metadata={"source": "api_request"}
            )
            
        except ValueError as e:
            logger.error(f"Invalid change type: {change_type}")
            return None
    
    async def _monitor_changes(self):
        """Monitor configuration changes và notify subscribers"""
        self._monitoring = True
        
        while self._monitoring:
            try:
                # Process changes from queue
                change = await asyncio.wait_for(
                    self._change_queue.get(), 
                    timeout=1.0
                )
                
                await self._process_config_change(change)
                
            except asyncio.TimeoutError:
                # No changes in queue, continue monitoring
                continue
            except Exception as e:
                logger.error(f"Error monitoring config changes: {e}")
                await asyncio.sleep(1)
    
    async def _process_config_change(self, change: ConfigChange):
        """Process a configuration change"""
        try:
            logger.info(f"Processing config change: {change.change_type} for {change.component_name}")
            
            await self._notify_subscribers(change)
            
            logger.info(f"Config change processed successfully: {change.component_name}")
            
        except Exception as e:
            logger.error(f"Failed to process config change: {e}")
    
    async def _apply_setting_change(self, change: ConfigChange) -> bool:
        """Apply change to settings object"""
        try:
            if change.change_type == ConfigChangeType.PROVIDER_ENABLED:
                if hasattr(self._current_settings, 'llm_providers') and change.component_name in self._current_settings.llm_providers:
                    self._current_settings.llm_providers[change.component_name].enabled = True
                    
            elif change.change_type == ConfigChangeType.PROVIDER_DISABLED:
                if hasattr(self._current_settings, 'llm_providers') and change.component_name in self._current_settings.llm_providers:
                    self._current_settings.llm_providers[change.component_name].enabled = False
                    
            elif change.change_type == ConfigChangeType.TOOL_ENABLED:
                # Tool settings được handle qua environment variables
                # Có thể implement dynamic tool settings nếu cần
                pass
                    
            elif change.change_type == ConfigChangeType.TOOL_DISABLED:
                # Tool settings được handle qua environment variables
                pass
                    
            elif change.change_type == ConfigChangeType.AGENT_ENABLED:
                if hasattr(self._current_settings, 'agents') and change.component_name in self._current_settings.agents:
                    self._current_settings.agents[change.component_name].enabled = True
                    
            elif change.change_type == ConfigChangeType.AGENT_DISABLED:
                if hasattr(self._current_settings, 'agents') and change.component_name in self._current_settings.agents:
                    self._current_settings.agents[change.component_name].enabled = False
            
            await self._persist_settings()
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to apply setting change: {e}")
            return False
    
    async def _persist_settings(self):
        """Persist settings to storage"""
        # TODO: Implement settings persistence if needed
        logger.info("Settings changes applied (in-memory)")
    
    async def _notify_subscribers(self, change: ConfigChange):
        """Notify subscribers about configuration change"""
        
        notify_components = []
        
        if change.change_type.name.startswith("PROVIDER_"):
            notify_components.extend(["llm_provider_manager", "workflow"])
            
        elif change.change_type.name.startswith("TOOL_"):
            notify_components.extend(["tool_manager", "workflow"])
            
        elif change.change_type.name.startswith("AGENT_"):
            notify_components.extend(["agent_orchestrator", "workflow"])
            
        elif change.change_type.name.startswith("WORKFLOW_"):
            notify_components.append("workflow")
        
        for component in notify_components:
            if component in self._subscribers:
                for subscriber in self._subscribers[component]:
                    try:
                        await subscriber.on_config_change(change)
                    except Exception as e:
                        logger.error(f"Subscriber {component} failed to handle config change: {e}")
    
    async def get_current_config(self) -> Dict[str, Any]:
        """Get current configuration state"""
        if not self._current_settings:
            self._current_settings = get_settings()
        
        config = {}
        
        # Providers
        if hasattr(self._current_settings, 'llm_providers') and self._current_settings.llm_providers:
            config["providers"] = {
                name: {
                    "enabled": config.enabled,
                    "models": config.models,
                    "default_model": config.default_model
                }
                for name, config in self._current_settings.llm_providers.items()
            }
        
        # Tools (from tool manager)
        tools_summary = tool_manager.get_tools_summary()
        enabled_tools = tool_manager.get_enabled_tools()
        config["tools"] = {
            "enabled_tools": enabled_tools,
            "total_tools": tools_summary.get("total_tools", 0),
            "system_tools": tools_summary.get("system_tools", 0),
            "agent_tools": tools_summary.get("agent_tools", 0)
        }
        
        # Agents
        if hasattr(self._current_settings, 'agents') and self._current_settings.agents:
            config["agents"] = {
                name: {
                    "enabled": config.enabled,
                    "domain": config.domain,
                    "capabilities": config.capabilities,
                    "model": config.model
                }
                for name, config in self._current_settings.agents.items()
            }
        
        # Workflow
        if hasattr(self._current_settings, 'workflow') and self._current_settings.workflow:
            config["workflow"] = {
                "max_iterations": self._current_settings.workflow.max_iterations,
                "timeout_seconds": self._current_settings.workflow.timeout_seconds,
                "enable_reflection": self._current_settings.workflow.enable_reflection,
                "enable_semantic_routing": self._current_settings.workflow.enable_semantic_routing,
                "checkpointer_type": self._current_settings.workflow.checkpointer_type
            }
        
        # Orchestrator
        if hasattr(self._current_settings, 'orchestrator') and self._current_settings.orchestrator:
            config["orchestrator"] = self._current_settings.orchestrator
        
        return config
    
    async def stop_monitoring(self):
        """Stop configuration monitoring"""
        self._monitoring = False
        logger.info("Configuration monitoring stopped")

config_manager = ConfigManager()