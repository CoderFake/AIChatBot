"""
Orchestrator Service - Refactored
Database-driven orchestration using AgentService
No hardcoded agents, loads from database
"""

from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
import json
import asyncio

from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from langchain_core.prompts import ChatPromptTemplate

from services.llm.provider_manager import llm_provider_manager
from services.types import QueryType, ExecutionStrategy
from services.dataclasses.orchestrator import QueryAnalysis, TaskDistribution, ToolSelection, ConflictResolution
from services.tools.tool_manager import tool_manager
from services.vector.milvus_service import milvus_service
from services.auth.permission_service import PermissionService
from services.agents.agent_service import AgentService
from agents.generic.dynamic_agent import DynamicAgent
from config.settings import get_settings
from utils.logging import get_logger

logger = get_logger(__name__)


class Orchestrator:
    """
    Database-driven orchestration service
    Uses AgentService to load agents dynamically from database
    """
    