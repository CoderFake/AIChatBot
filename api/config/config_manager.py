from typing import Dict, Any, List, Optional, Callable
import asyncio
import json
from datetime import datetime
from dataclasses import dataclass, field
from enum import Enum

from config.settings import get_settings, reload_settings, Settings
from utils.logging import get_logger

logger = get_logger(__name__)

class ConfigChangeType(Enum):
    """Types of configuration changes"""
    PROVIDER_ENABLED = "provider_enabled"
    PROVIDER_DISABLED = "provider_disabled"
    PROVIDER_CONFIG_CHANGED = "provider_config_changed"
    TOOL_ENABLED = "tool_enabled"
    TOOL_DISABLED = "tool_disabled"
    TOOL_CONFIG_CHANGED = "tool_config_changed"
    AGENT_ENABLED = "agent_enabled"
    AGENT_DISABLED = "agent_disabled"
    AGENT_CONFIG_CHANGED = "agent_config_changed"
    WORKFLOW_CONFIG_CHANGED = "workflow_config_changed"
    ORCHESTRATOR_CONFIG_CHANGED = "orchestrator_config_changed"

@dataclass
class ConfigChange:
    """Configuration change event"""
    change_type: ConfigChangeType
    component_name: str
    old_value: Any
    new_value: Any
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)

class ConfigSubscriber:
    """Base class for configuration subscribers"""
    
    async def on_config_change(self, change: ConfigChange) -> bool:
        """Handle configuration change"""
        return True

class ConfigManager:
    """
    Real-time configuration management
    Monitors và propagates configuration changes
    """
    
    def __init__(self):
        self._subscribers: Dict[str, List[ConfigSubscriber]] = {}
        self._current_settings: Optional[Settings] = None
        self._monitoring = False
        self._change_queue: asyncio.Queue = asyncio.Queue()
        
    async def initialize(self):
        """Initialize configuration manager"""
        try:
            self._current_settings = get_settings()
            
            asyncio.create_task(self._monitor_changes())
            
            logger.info("Configuration manager initialized")
            
        except Exception as e:
            logger.error(f"Failed to initialize config manager: {e}")
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
        Apply configuration change from admin API
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
            
            await self._change_queue.put(config_change)
            
            return {
                "success": True,
                "change_id": f"{component_name}_{datetime.now().timestamp()}",
                "message": f"Configuration change queued for {component_name}"
            }
            
        except Exception as e:
            logger.error(f"Failed to apply config change: {e}")
            return {"success": False, "error": str(e)}
    
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
                old_value = self._current_settings.llm_providers.get(component_name, {}).enabled
            elif change_enum in [ConfigChangeType.TOOL_ENABLED, ConfigChangeType.TOOL_DISABLED]:
                old_value = self._current_settings.tools.get(component_name, {}).get("enabled", False)
            elif change_enum in [ConfigChangeType.AGENT_ENABLED, ConfigChangeType.AGENT_DISABLED]:
                old_value = self._current_settings.agents.get(component_name, {}).enabled
            
            return ConfigChange(
                change_type=change_enum,
                component_name=component_name,
                old_value=old_value,
                new_value=new_config,
                metadata={"source": "admin_api"}
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
            
            # Apply change to current settings
            success = await self._apply_setting_change(change)
            
            if not success:
                logger.error(f"Failed to apply setting change: {change}")
                return
            
            # Notify relevant subscribers
            await self._notify_subscribers(change)
            
            logger.info(f"Config change processed successfully: {change.component_name}")
            
        except Exception as e:
            logger.error(f"Failed to process config change: {e}")
    
    async def _apply_setting_change(self, change: ConfigChange) -> bool:
        """Apply change to settings object"""
        try:
            # Update in-memory settings
            if change.change_type == ConfigChangeType.PROVIDER_ENABLED:
                if change.component_name in self._current_settings.llm_providers:
                    self._current_settings.llm_providers[change.component_name].enabled = True
                    
            elif change.change_type == ConfigChangeType.PROVIDER_DISABLED:
                if change.component_name in self._current_settings.llm_providers:
                    self._current_settings.llm_providers[change.component_name].enabled = False
                    
            elif change.change_type == ConfigChangeType.TOOL_ENABLED:
                if change.component_name in self._current_settings.tools:
                    self._current_settings.tools[change.component_name]["enabled"] = True
                    
            elif change.change_type == ConfigChangeType.TOOL_DISABLED:
                if change.component_name in self._current_settings.tools:
                    self._current_settings.tools[change.component_name]["enabled"] = False
                    
            elif change.change_type == ConfigChangeType.AGENT_ENABLED:
                if change.component_name in self._current_settings.agents:
                    self._current_settings.agents[change.component_name].enabled = True
                    
            elif change.change_type == ConfigChangeType.AGENT_DISABLED:
                if change.component_name in self._current_settings.agents:
                    self._current_settings.agents[change.component_name].enabled = False
            
            # Persist changes to file/database if needed
            await self._persist_settings()
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to apply setting change: {e}")
            return False
    
    async def _persist_settings(self):
        """Persist settings to storage"""
        # In production, this would save to database
        # For now, just log the change
        logger.info("Settings persisted (placeholder implementation)")
    
    async def _notify_subscribers(self, change: ConfigChange):
        """Notify subscribers about configuration change"""
        
        # Determine which components need to be notified
        notify_components = []
        
        if change.change_type.name.startswith("PROVIDER_"):
            notify_components.extend(["llm_provider_manager", "workflow"])
            
        elif change.change_type.name.startswith("TOOL_"):
            notify_components.extend(["tool_service", "workflow"])
            
        elif change.change_type.name.startswith("AGENT_"):
            notify_components.extend(["agent_orchestrator", "workflow"])
            
        elif change.change_type.name.startswith("WORKFLOW_"):
            notify_components.append("workflow")
        
        # Notify all relevant subscribers
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
        
        return {
            "providers": {
                name: {
                    "enabled": config.enabled,
                    "models": config.models,
                    "default_model": config.default_model
                }
                for name, config in self._current_settings.llm_providers.items()
            },
            "tools": {
                name: config for name, config in self._current_settings.tools.items()
            },
            "agents": {
                name: {
                    "enabled": config.enabled,
                    "domain": config.domain,
                    "capabilities": config.capabilities,
                    "model": config.model
                }
                for name, config in self._current_settings.agents.items()
            },
            "workflow": {
                "max_iterations": self._current_settings.workflow.max_iterations,
                "timeout_seconds": self._current_settings.workflow.timeout_seconds,
                "enable_reflection": self._current_settings.workflow.enable_reflection,
                "enable_semantic_routing": self._current_settings.workflow.enable_semantic_routing,
                "checkpointer_type": self._current_settings.workflow.checkpointer_type
            },
            "orchestrator": self._current_settings.orchestrator
        }
    
    async def stop_monitoring(self):
        """Stop configuration monitoring"""
        self._monitoring = False
        logger.info("Configuration monitoring stopped")

config_manager = ConfigManager()