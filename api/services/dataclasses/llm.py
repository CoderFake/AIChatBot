from dataclasses import dataclass
from typing import Dict, Any


@dataclass
class LLMResponse:
    """Standard LLM response wrapper"""
    content: str
    model: str
    provider: str
    usage: Dict[str, Any] = None
    metadata: Dict[str, Any] = None