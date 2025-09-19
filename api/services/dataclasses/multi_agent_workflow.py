from dataclasses import dataclass
from typing import List, Optional
from datetime import datetime
from services.types import AgentRole, ConflictLevel


@dataclass
class AgentResponse:
    """Response from an agent"""
    agent_role: AgentRole
    content: str
    confidence: float 
    evidence: List[str]
    tools_used: List[str]
    execution_time: float
    timestamp: datetime

@dataclass 
class ConflictResolution:
    """Result of conflict resolution"""
    conflict_level: ConflictLevel
    resolution_method: str 
    winner_agent: Optional[AgentRole] = None
    synthesized_result: Optional[str] = None
    consensus_score: float = 0.0
    resolution_explanation: str = ""
