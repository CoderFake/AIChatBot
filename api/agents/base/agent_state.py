from typing import Dict, List, Any, Optional, Union, Annotated
from datetime import datetime
from dataclasses import dataclass, field
from enum import Enum
from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages
from pydantic import BaseModel

class AgentRole(Enum):
    """Vai trò của các agents trong hệ thống"""
    COORDINATOR = "coordinator"           # Điều phối tổng thể
    HR_SPECIALIST = "hr_specialist"       # Chuyên gia HR
    FINANCE_SPECIALIST = "finance_specialist"  # Chuyên gia Finance
    IT_SPECIALIST = "it_specialist"       # Chuyên gia IT
    GENERAL_ASSISTANT = "general_assistant"    # Trợ lý tổng quát
    CONFLICT_RESOLVER = "conflict_resolver"    # Giải quyết xung đột
    SYNTHESIZER = "synthesizer"           # Tổng hợp kết quả

class ConflictType(Enum):
    """Loại xung đột giữa các agents"""
    INFORMATION_MISMATCH = "information_mismatch"  # Thông tin không khớp
    APPROACH_DIFFERENCE = "approach_difference"    # Cách tiếp cận khác nhau
    PRIORITY_CONFLICT = "priority_conflict"        # Xung đột về ưu tiên
    RESOURCE_COMPETITION = "resource_competition"   # Cạnh tranh tài nguyên

class TaskStatus(Enum):
    """Trạng thái của task"""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CONFLICTED = "conflicted"
    RESOLVED = "resolved"
    FAILED = "failed"

@dataclass
class AgentResponse:
    """Response từ mỗi agent"""
    agent_id: str
    role: AgentRole
    content: str
    confidence: float  # 0.0 - 1.0
    evidence: List[str] = field(default_factory=list)  # Supporting evidence
    sources: List[str] = field(default_factory=list)   # Data sources used
    timestamp: datetime = field(default_factory=datetime.now)
    reasoning: Optional[str] = None  # Chain of thought
    
class AgentTask:
    """Task được giao cho agent"""
    def __init__(
        self, 
        task_id: str,
        agent_role: AgentRole,
        description: str,
        priority: int = 1,
        depends_on: List[str] = None
    ):
        self.task_id = task_id
        self.agent_role = agent_role
        self.description = description
        self.priority = priority
        self.depends_on = depends_on or []
        self.status = TaskStatus.PENDING
        self.result: Optional[AgentResponse] = None
        self.created_at = datetime.now()

@dataclass
class ConflictReport:
    """Báo cáo xung đột giữa agents"""
    conflict_id: str
    conflict_type: ConflictType
    involved_agents: List[str]
    conflicting_responses: List[AgentResponse]
    description: str
    severity: float  # 0.0 - 1.0
    detected_at: datetime = field(default_factory=datetime.now)
    resolution_strategy: Optional[str] = None
    is_resolved: bool = False

@dataclass 
class ConsensusResult:
    """Kết quả đồng thuận từ các agents"""
    primary_response: AgentResponse
    supporting_responses: List[AgentResponse]
    consensus_confidence: float  # 0.0 - 1.0
    agreement_level: float       # 0.0 - 1.0 
    synthesis_notes: Optional[str] = None
    minority_opinions: List[AgentResponse] = field(default_factory=list)

class MultiAgentState(BaseModel):
    """
    State chính cho hệ thống Multi-Agent Agentic RAG
    Tracking toàn bộ conversation, tasks, conflicts và consensus
    """
    
    # Core conversation
    messages: Annotated[List[BaseMessage], add_messages] = []
    
    # Query processing
    original_query: str = ""
    processed_query: str = ""
    query_complexity: float = 0.0  # 0.0 = simple, 1.0 = very complex
    required_domains: List[str] = []  # ["hr", "finance", "it"]
    
    # Agent management  
    active_agents: Dict[str, AgentRole] = {}  # agent_id -> role
    agent_tasks: Dict[str, AgentTask] = {}    # task_id -> task
    agent_responses: Dict[str, List[AgentResponse]] = {}  # agent_id -> responses
    
    # Collaboration & Conflict
    conflicts: List[ConflictReport] = []
    consensus_results: List[ConsensusResult] = []
    current_phase: str = "analysis"  # analysis, delegation, execution, deliberation, resolution, synthesis
    
    # Resource sharing
    shared_documents: Dict[str, Any] = {}     # document_id -> content
    shared_knowledge: Dict[str, Any] = {}     # key -> knowledge
    cross_domain_insights: List[str] = []
    
    # Performance tracking
    iteration_count: int = 0
    max_iterations: int = 10
    start_time: datetime = datetime.now()
    phase_timestamps: Dict[str, datetime] = {}
    
    # Final output
    final_response: Optional[str] = None
    response_confidence: float = 0.0
    supporting_evidence: List[str] = []
    
    class Config:
        arbitrary_types_allowed = True

# Helper functions cho state operations
def add_agent_response(state: MultiAgentState, response: AgentResponse) -> Dict[str, Any]:
    """Thêm response từ agent vào state"""
    if response.agent_id not in state.agent_responses:
        state.agent_responses[response.agent_id] = []
    
    state.agent_responses[response.agent_id].append(response)
    
    return {
        "agent_responses": state.agent_responses
    }

def detect_potential_conflicts(state: MultiAgentState) -> List[ConflictReport]:
    """Phát hiện conflicts tiềm tàng giữa agent responses"""
    conflicts = []
    
    # So sánh responses từ các agents khác nhau
    agent_ids = list(state.agent_responses.keys())
    
    for i in range(len(agent_ids)):
        for j in range(i + 1, len(agent_ids)):
            agent1_id = agent_ids[i]
            agent2_id = agent_ids[j]
            
            responses1 = state.agent_responses[agent1_id]
            responses2 = state.agent_responses[agent2_id]
            
            # Check latest responses
            if responses1 and responses2:
                latest1 = responses1[-1]
                latest2 = responses2[-1]
                
                # Conflict detection logic
                confidence_diff = abs(latest1.confidence - latest2.confidence)
                content_similarity = calculate_content_similarity(latest1.content, latest2.content)
                
                if confidence_diff > 0.3 and content_similarity < 0.5:
                    conflict = ConflictReport(
                        conflict_id=f"conflict_{agent1_id}_{agent2_id}_{datetime.now().timestamp()}",
                        conflict_type=ConflictType.INFORMATION_MISMATCH,
                        involved_agents=[agent1_id, agent2_id],
                        conflicting_responses=[latest1, latest2],
                        description=f"High confidence responses with low content similarity",
                        severity=confidence_diff
                    )
                    conflicts.append(conflict)
    
    return conflicts

def calculate_content_similarity(content1: str, content2: str) -> float:
    """Tính similarity giữa hai response contents (placeholder)"""
    # Implement actual similarity calculation
    # For now, simple word overlap
    words1 = set(content1.lower().split())
    words2 = set(content2.lower().split())
    
    if not words1 or not words2:
        return 0.0
    
    intersection = words1.intersection(words2)
    union = words1.union(words2)
    
    return len(intersection) / len(union) if union else 0.0

def build_consensus(responses: List[AgentResponse]) -> ConsensusResult:
    """Xây dựng consensus từ multiple agent responses"""
    if not responses:
        raise ValueError("Không có response nào để build consensus")
    
    # Sort by confidence
    sorted_responses = sorted(responses, key=lambda r: r.confidence, reverse=True)
    primary_response = sorted_responses[0]
    
    # Calculate agreement level
    high_confidence_responses = [r for r in responses if r.confidence > 0.7]
    agreement_level = len(high_confidence_responses) / len(responses)
    
    # Calculate consensus confidence
    avg_confidence = sum(r.confidence for r in responses) / len(responses)
    consensus_confidence = avg_confidence * agreement_level
    
    return ConsensusResult(
        primary_response=primary_response,
        supporting_responses=sorted_responses[1:],
        consensus_confidence=consensus_confidence,
        agreement_level=agreement_level,
        minority_opinions=[r for r in responses if r.confidence < 0.5]
    )
