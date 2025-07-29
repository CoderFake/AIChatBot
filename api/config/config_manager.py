"""
Configuration Manager
Database-driven configuration, no hardcoded agents/tools
Load everything from database via services
"""

from typing import Dict, Any, List, Optional
import asyncio
from datetime import datetime

from sqlalchemy.orm import Session
from config.settings import get_settings, Settings
from services.agents.agent_service import AgentService
from config.database import get_db
from utils.logging import get_logger

logger = get_logger(__name__)


class ConfigManager:
    """
    Database-driven configuration manager
    Loads all configuration from database, no hardcoded values
    """
    
    def __init__(self):
        self._current_settings: Optional[Settings] = None
        self._monitoring = False
        self._last_update = None
        
        self._load_settings()
    
    def _load_settings(self) -> None:
        """Load settings from environment/config files"""
        try:
            self._current_settings = get_settings()
            logger.info("Configuration loaded successfully")
        except Exception as e:
            logger.error(f"Failed to load configuration: {e}")
            self._current_settings = Settings() 
    
    def _get_db_session(self) -> Optional[Session]:
        """Get database session"""
        try:
            db = next(get_db())
            return db
        except Exception as e:
            logger.error(f"Failed to get database session: {e}")
            return None
    
    def get_db_agents(self, db: Session) -> List[Dict[str, Any]]:
        """Get agents from database"""
        try:
            agent_service = AgentService(db)
            agents = agent_service.get_agents_for_selection()
            
            formatted_agents = []
            for agent in agents:
                formatted_agents.append({
                    "name": agent["code"],
                    "display_name": agent["name"],
                    "description": agent["description"],
                    "is_enabled": True,
                    "source": "database_primary"
                })
            
            return formatted_agents
            
        except Exception as e:
            logger.error(f"Failed to get agents from database: {e}")
            return []
    
    def get_db_tools(self, db: Session) -> List[Dict[str, Any]]:
        """Get tools from database"""
        try:
            from services.tools.tool_service import ToolService
            
            tool_service = ToolService(db)
            tools = tool_service.get_all_enabled_tools()
            
            formatted_tools = []
            for tool in tools:
                formatted_tools.append({
                    "name": tool.get("tool_code", tool.get("name")),
                    "display_name": tool.get("tool_name", tool.get("display_name")),
                    "category": tool.get("category", "utility_tools"),
                    "description": tool.get("description", ""),
                    "is_enabled": tool.get("is_enabled", True),
                    "source": "database_primary"
                })
            
            return formatted_tools
            
        except Exception as e:
            logger.error(f"Failed to get tools from database: {e}")
            return []
    
    def get_db_providers(self, db: Session) -> List[Dict[str, Any]]:
        """Get providers from database"""
        try:
            from services.providers.provider_service import ProviderService
            
            provider_service = ProviderService(db)
            providers = provider_service.get_all_enabled_providers()
            
            formatted_providers = []
            for provider in providers:
                formatted_providers.append({
                    "name": provider.get("provider_code", provider.get("name")),
                    "display_name": provider.get("provider_name", provider.get("display_name")),
                    "is_enabled": provider.get("is_enabled", True),
                    "config": provider.get("base_config", {}),
                    "source": "database_primary"
                })
            
            return formatted_providers
            
        except Exception as e:
            logger.error(f"Failed to get providers from database: {e}")
            return []
    
    def _format_config_response(
        self, 
        data: List[Dict], 
        source: str, 
        message: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """Format configuration response"""
        response = {
            "data": data,
            "source": source,
            "count": len(data),
            "last_updated": datetime.now().isoformat()
        }
        
        if message:
            response["message"] = message
        
        for key, value in kwargs.items():
            response[key] = value
        
        return response
    
    def get_current_config(self) -> Dict[str, Any]:
        """
        Get current system configuration from database
        No hardcoded fallbacks - everything from DB
        """
        config = {}
        db = self._get_db_session()
        
        if db:
            try:
                all_providers = self.get_db_providers(db)
                config["providers"] = self._format_config_response(
                    all_providers, "database_primary"
                )
            except Exception as e:
                logger.warning(f"Database providers failed: {e}")
                config["providers"] = self._format_config_response(
                    [], "database_unavailable", "Database connection failed"
                )
        else:
            config["providers"] = self._format_config_response(
                [], "database_unavailable", "Database connection failed"
            )
        
        if db:
            try:
                all_tools = self.get_db_tools(db)
                categories = list(set([tool["category"] for tool in all_tools]))
                config["tools"] = self._format_config_response(
                    all_tools, "database_primary", categories=categories
                )
            except Exception as e:
                logger.warning(f"Database tools failed: {e}")
                config["tools"] = self._format_config_response(
                    [], "database_unavailable", "Database connection failed"
                )
        else:
            config["tools"] = self._format_config_response(
                [], "database_unavailable", "Database connection failed"
            )
        
        if db:
            try:
                all_agents = self.get_db_agents(db)
                config["agents"] = self._format_config_response(
                    all_agents, "database_primary"
                )
            except Exception as e:
                logger.warning(f"Database agents failed: {e}")
                config["agents"] = self._format_config_response(
                    [], "database_unavailable", "Database connection failed"
                )
        else:
            config["agents"] = self._format_config_response(
                [], "database_unavailable", "Database connection failed"
            )
        
        if hasattr(self._current_settings, 'workflow') and self._current_settings.workflow:
            config["workflow"] = {
                "max_iterations": self._current_settings.workflow.max_iterations,
                "timeout_seconds": self._current_settings.workflow.timeout_seconds,
                "enable_reflection": self._current_settings.workflow.enable_reflection,
                "enable_semantic_routing": self._current_settings.workflow.enable_semantic_routing,
                "checkpointer_type": self._current_settings.workflow.checkpointer_type
            }
        
        if hasattr(self._current_settings, 'orchestrator') and self._current_settings.orchestrator:
            config["orchestrator"] = self._current_settings.orchestrator
        
        if db:
            db.close()
        
        return config
    
    async def start_monitoring(self):
        """Start configuration monitoring"""
        self._monitoring = True
        logger.info("Configuration monitoring started")
        
        while self._monitoring:
            try:
                await asyncio.sleep(300)
                
                new_config = self.get_current_config()
                self._last_update = datetime.now()
                
                logger.debug("Configuration refreshed from database")
                
            except Exception as e:
                logger.error(f"Configuration monitoring error: {e}")
                await asyncio.sleep(60) 
    
    async def stop_monitoring(self):
        """Stop configuration monitoring"""
        self._monitoring = False
        logger.info("Configuration monitoring stopped")


config_manager = ConfigManager()