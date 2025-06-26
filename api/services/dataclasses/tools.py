from dataclasses import dataclass
from typing import Optional

@dataclass
class ToolUsageStats:
    """Statistics cho tool usage"""
    tool_name: str
    usage_count: int = 0
    success_count: int = 0
    error_count: int = 0
    avg_execution_time: float = 0.0
    last_used: Optional[str] = None