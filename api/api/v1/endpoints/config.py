
from fastapi import APIRouter, HTTPException, Depends, status
from typing import Dict, Any, List, Optional
from config.config_manager import config_manager
from services.llm.provider_manager import llm_provider_manager
from services.tools.tool_manager import tool_manager
from utils.logging import get_logger

router = APIRouter()
logger = get_logger(__name__)

#get health, current config, update config in cache
