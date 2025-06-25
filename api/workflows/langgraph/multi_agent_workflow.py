from typing import Dict, List, Any, Optional, Union, Literal, Annotated
from datetime import datetime
from dataclasses import dataclass
from enum import Enum

from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage
from langgraph.graph import StateGraph, START, END, MessagesState
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode
from pydantic import BaseModel, Field

from config.settings import get_settings
from services.llm.provider_manager import llm_provider_manager
from services.tools.tool_manager import tool_manager
from services.orchestrator.agent_orchestrator import IntelligentAgentOrchestrator, AgentDomain
from utils.logging import get_logger

logger = get_logger(__name__)
settings = get_settings()

class AgentRole(Enum):
    """Vai trò của các agents trong hệ thống"""
    COORDINATOR = "coordinator"
    HR_SPECIALIST = "hr_specialist" 
    FINANCE_SPECIALIST = "finance_specialist"
    IT_SPECIALIST = "it_specialist"
    GENERAL_ASSISTANT = "general_assistant"
    CONFLICT_RESOLVER = "conflict_resolver"
    SYNTHESIZER = "synthesizer"

class ConflictLevel(Enum):
    """Mức độ xung đột giữa các agents"""
    NONE = "none"
    LOW = "low"      # Confidence gap < 0.3
    MEDIUM = "medium" # Confidence gap 0.3-0.6
    HIGH = "high"    # Confidence gap > 0.6

class ConsensusStatus(Enum):
    """Trạng thái đồng thuận"""
    PENDING = "pending"
    ACHIEVED = "achieved" 
    FAILED = "failed"
    ESCALATED = "escalated"

@dataclass
class AgentResponse:
    """Response từ một agent"""
    agent_role: AgentRole
    content: str
    confidence: float  # 0.0 - 1.0
    evidence: List[str]
    tools_used: List[str]
    execution_time: float
    timestamp: datetime

@dataclass 
class ConflictResolution:
    """Kết quả giải quyết xung đột"""
    conflict_level: ConflictLevel
    resolution_method: str  # "evidence_based", "synthesis", "voting", "escalation"
    winner_agent: Optional[AgentRole] = None
    synthesized_result: Optional[str] = None
    consensus_score: float = 0.0
    resolution_explanation: str = ""

class MultiAgentState(TypedDict):
    """State cho multi-agent workflow"""
    # Input
    original_query: str
    language: str
    user_context: Dict[str, Any]
    
    # Orchestrator Analysis (LLM-driven)
    orchestrator_analysis: Optional[Dict[str, Any]]
    selected_agents: List[AgentDomain]
    complexity_score: float
    is_cross_domain: bool
    
    # Task delegation 
    delegated_tasks: Dict[str, Dict[str, Any]]
    
    # Agent responses
    agent_responses: Dict[str, Any]
    response_confidences: Dict[str, float]
    evidence_sources: Dict[str, List[str]]
    
    # Conflict analysis
    conflicts_detected: List[Dict[str, Any]]
    conflict_level: ConflictLevel
    
    # Resolution
    conflict_resolutions: List[Dict[str, Any]]
    consensus_status: ConsensusStatus
    
    # Final synthesis
    final_response: Optional[str]
    combined_confidence: float
    all_evidence: List[str]
    
    # Workflow control
    current_phase: str
    execution_metadata: Dict[str, Any]
    
    # Messages for LangGraph
    messages: Annotated[List[BaseMessage], add_messages]

# ================================
# WORKFLOW NODES (Updated with LLM Orchestrator)  
# ================================

async def analyze_query_with_llm_orchestrator(state: MultiAgentState) -> MultiAgentState:
    """
    🧠 Giai đoạn 1: Intelligent Agent Selection sử dụng LLM Orchestrator
    Thay thế hardcode keywords bằng LLM semantic analysis
    """
    logger.info("🧠 Starting LLM Orchestrator analysis...")
    
    query = state["original_query"]
    language = state.get("language", "vi")
    user_context = state.get("user_context", {})
    
    # Check if intelligent orchestrator is enabled
    if not getattr(settings, 'ENABLE_INTELLIGENT_ORCHESTRATOR', True):
        logger.warning("Intelligent orchestrator disabled, falling back to default agent")
        return {
            "orchestrator_analysis": {"method": "fallback", "reason": "orchestrator_disabled"},
            "selected_agents": [AgentDomain.GENERAL],
            "complexity_score": 0.5,
            "is_cross_domain": False,
            "current_phase": "delegation",
            **state
        }
    
    try:
        # Initialize LLM Orchestrator
        orchestrator = IntelligentAgentOrchestrator()
        
        # Prepare context for orchestrator
        orchestrator_context = {
            "conversation_summary": user_context.get("conversation_history", ""),
            "user_preferences": user_context.get("preferences", {}),
            "session_context": user_context.get("session_info", {})
        }
        
        # LLM analyzes and selects agents
        selection_result = await orchestrator.analyze_and_select_agents(
            query=query,
            language=language,
            context=orchestrator_context
        )
        
        # Generate explanation for transparency
        explanation = await orchestrator.explain_selection(selection_result, language)
        
        logger.info(f"✅ Orchestrator selected: {[agent.value for agent in selection_result.selected_agents]} "
                   f"(confidence: {selection_result.confidence:.2f})")
        
        return {
            "orchestrator_analysis": {
                "method": "llm_orchestrator",
                "selection_result": selection_result.__dict__,
                "explanation": explanation,
                "reasoning": selection_result.reasoning
            },
            "selected_agents": selection_result.selected_agents,
            "complexity_score": selection_result.complexity_score,
            "is_cross_domain": selection_result.is_cross_domain,
            "current_phase": "delegation",
            **state
        }
        
    except Exception as e:
        logger.error(f"❌ LLM Orchestrator failed: {e}")
        
        # Fallback to keyword-based selection
        logger.info("🔄 Falling back to keyword-based agent selection...")
        fallback_agents = await _fallback_keyword_selection(query, language)
        
        return {
            "orchestrator_analysis": {
                "method": "keyword_fallback", 
                "reason": f"orchestrator_error: {str(e)}",
                "fallback_agents": [agent.value for agent in fallback_agents]
            },
            "selected_agents": fallback_agents,
            "complexity_score": 0.6,
            "is_cross_domain": len(fallback_agents) > 1,
            "current_phase": "delegation",
            **state
        }

async def delegate_tasks_intelligently(state: MultiAgentState) -> MultiAgentState:
    """
    📋 Giai đoạn 2: Smart Task Delegation dựa trên LLM analysis
    Phân chia tasks cụ thể cho từng agent được chọn
    """
    logger.info("📋 Intelligently delegating tasks to selected agents...")
    
    query = state["original_query"]
    selected_agents = state["selected_agents"]
    orchestrator_analysis = state.get("orchestrator_analysis", {})
    
    # Get enabled tools from admin settings
    enabled_tools = getattr(settings, 'enabled_tools', {})
    available_tools = [tool for tool, enabled in enabled_tools.items() if enabled]
    
    # Intelligent task delegation based on agent domains
    delegated_tasks = {}
    
    for agent_domain in selected_agents:
        if agent_domain == AgentDomain.HR:
            delegated_tasks["hr_specialist"] = {
                "task": f"Analyze HR policies, employee benefits, workplace regulations related to: {query}",
                "priority": "high",
                "tools_suggested": ["document_search_tool", "web_search_tool"],
                "focus_areas": ["policies", "benefits", "compliance", "employee_relations"],
                "expected_deliverables": ["policy_references", "compliance_requirements", "employee_impact"]
            }
            
        elif agent_domain == AgentDomain.FINANCE:
            delegated_tasks["finance_specialist"] = {
                "task": f"Analyze financial implications, cost impact, budget considerations for: {query}",
                "priority": "high",
                "tools_suggested": ["document_search_tool", "calculation_tool", "web_search_tool"],
                "focus_areas": ["budget_impact", "cost_analysis", "financial_compliance", "roi_assessment"],
                "expected_deliverables": ["cost_breakdown", "budget_implications", "financial_recommendations"]
            }
            
        elif agent_domain == AgentDomain.IT:
            delegated_tasks["it_specialist"] = {
                "task": f"Analyze technology systems, infrastructure, security implications for: {query}",
                "priority": "medium",
                "tools_suggested": ["document_search_tool", "web_search_tool", "code_generation_tool"],
                "focus_areas": ["system_requirements", "security_considerations", "technical_feasibility", "infrastructure_impact"],
                "expected_deliverables": ["technical_requirements", "security_assessment", "implementation_roadmap"]
            }
            
        else:  # GENERAL
            delegated_tasks["general_assistant"] = {
                "task": f"Provide comprehensive research and analysis for: {query}",
                "priority": "medium",
                "tools_suggested": ["web_search_tool", "document_search_tool", "translation_tool"],
                "focus_areas": ["general_research", "background_information", "context_analysis"],
                "expected_deliverables": ["research_summary", "relevant_context", "supporting_information"]
            }
    
    # Add metadata về delegation strategy
    delegation_metadata = {
        "strategy": "llm_orchestrator_based",
        "agent_count": len(selected_agents),
        "complexity_score": state.get("complexity_score", 0.5),
        "cross_domain": state.get("is_cross_domain", False),
        "available_tools": available_tools,
        "delegation_timestamp": datetime.now().isoformat()
    }
    
    logger.info(f"✅ Delegated tasks to {len(delegated_tasks)} agents: {list(delegated_tasks.keys())}")
    
    return {
        "delegated_tasks": delegated_tasks,
        "current_phase": "execution",
        "execution_metadata": delegation_metadata,
        **state
    }

# ================================ 
# HELPER FUNCTIONS
# ================================

async def _fallback_keyword_selection(query: str, language: str) -> List[AgentDomain]:
    """
    Fallback agent selection sử dụng keyword matching
    Chỉ dùng khi LLM orchestrator fails
    """
    logger.info("🔄 Using fallback keyword-based agent selection...")
    
    query_lower = query.lower()
    selected_agents = []
    
    # Get keywords từ settings (deprecated nhưng vẫn giữ cho fallback)
    hr_keywords = getattr(settings, 'HR_KEYWORDS', {}).get(language, [])
    finance_keywords = getattr(settings, 'FINANCE_KEYWORDS', {}).get(language, [])
    it_keywords = getattr(settings, 'IT_KEYWORDS', {}).get(language, [])
    
    # Check HR keywords
    if any(keyword.lower() in query_lower for keyword in hr_keywords):
        selected_agents.append(AgentDomain.HR)
        
    # Check Finance keywords  
    if any(keyword.lower() in query_lower for keyword in finance_keywords):
        selected_agents.append(AgentDomain.FINANCE)
        
    # Check IT keywords
    if any(keyword.lower() in query_lower for keyword in it_keywords):
        selected_agents.append(AgentDomain.IT)
    
    # Fallback to general assistant if no specific domain detected
    if not selected_agents:
        selected_agents.append(AgentDomain.GENERAL)
    
    logger.info(f"🎯 Keyword fallback selected: {[agent.value for agent in selected_agents]}")
    return selected_agents

async def execute_specialist_agents(state: MultiAgentState) -> MultiAgentState:
    """
    ⚡ Giai đoạn 3: Execution các specialist agents song song
    Thực hiện tasks được delegate cho từng agent
    """
    logger.info("⚡ Executing specialist agents in parallel...")
    
    delegated_tasks = state["delegated_tasks"]
    agent_responses = {}
    response_confidences = {}
    evidence_sources = {}
    
    # Execute each agent's task in parallel
    for agent_name, task_info in delegated_tasks.items():
        try:
            logger.info(f"🔄 Executing {agent_name}...")
            
            # Get agent domain from name
            if "hr" in agent_name:
                agent_domain = AgentDomain.HR
            elif "finance" in agent_name:
                agent_domain = AgentDomain.FINANCE
            elif "it" in agent_name:
                agent_domain = AgentDomain.IT
            else:
                agent_domain = AgentDomain.GENERAL
            
            # Execute agent task
            response, confidence, evidence, tools_used = await _execute_agent_task(
                agent_domain, task_info["task"], state
            )
            
            agent_responses[agent_name] = {
                "response": response,
                "tools_used": tools_used,
                "execution_time": datetime.now().isoformat(),
                "focus_areas": task_info.get("focus_areas", []),
                "deliverables": task_info.get("expected_deliverables", [])
            }
            
            response_confidences[agent_name] = confidence
            evidence_sources[agent_name] = evidence
            
            logger.info(f"✅ {agent_name} completed (confidence: {confidence:.2f})")
            
        except Exception as e:
            logger.error(f"❌ {agent_name} execution failed: {e}")
            
            agent_responses[agent_name] = {
                "response": f"Error executing {agent_name}: {str(e)}",
                "tools_used": [],
                "execution_time": datetime.now().isoformat(),
                "error": True
            }
            response_confidences[agent_name] = 0.1
            evidence_sources[agent_name] = []
    
    return {
        "agent_responses": agent_responses,
        "response_confidences": response_confidences,
        "evidence_sources": evidence_sources,
        "current_phase": "conflict_detection",
        **state
    }

async def _execute_agent_task(
    agent_domain: AgentDomain, 
    task: str, 
    state: MultiAgentState
) -> tuple[str, float, List[str], List[str]]:
    """Execute task for specific agent domain using LLM"""
    
    # Get enabled tools from admin
    enabled_tools = getattr(settings, 'enabled_tools', {})
    available_tools = [tool for tool, enabled in enabled_tools.items() if enabled]
    
    # Get LLM provider for agent execution
    enabled_providers = getattr(settings, 'enabled_providers', [])
    if not enabled_providers:
        raise ValueError("No LLM providers enabled")
        
    llm = await llm_provider_manager.get_provider(enabled_providers[0])
    
    # Domain-specific prompts and execution
    if agent_domain == AgentDomain.HR:
        execution_prompt = f"""
You are an HR Specialist. Analyze the following task from HR perspective:

Task: {task}

Focus on:
- HR policies and procedures
- Employee benefits and compensation
- Compliance requirements
- Workplace regulations
- Employee impact assessment

Available tools: {', '.join(available_tools)}

Provide detailed analysis with:
1. Policy recommendations
2. Compliance considerations  
3. Employee impact
4. Implementation guidance

Response in Vietnamese:
"""
        confidence = 0.85
        evidence = ["HR Policy Database", "Employee Handbook", "Compliance Guidelines"]
        tools_used = ["document_search_tool", "web_search_tool"]
        
    elif agent_domain == AgentDomain.FINANCE:
        execution_prompt = f"""
You are a Finance Specialist. Analyze the following task from financial perspective:

Task: {task}

Focus on:
- Budget impact and cost analysis
- Financial compliance requirements
- ROI and cost-benefit analysis
- Financial risk assessment

Available tools: {', '.join(available_tools)}

Provide detailed analysis with:
1. Cost breakdown
2. Budget implications
3. Financial recommendations
4. Risk assessment

Response in Vietnamese:
"""
        confidence = 0.80
        evidence = ["Financial Reports", "Budget Documents", "Cost Analysis"]
        tools_used = ["document_search_tool", "calculation_tool"]
        
    elif agent_domain == AgentDomain.IT:
        execution_prompt = f"""
You are an IT Specialist. Analyze the following task from technology perspective:

Task: {task}

Focus on:
- Technical requirements and feasibility
- System architecture and infrastructure
- Security considerations
- Implementation roadmap

Available tools: {', '.join(available_tools)}

Provide detailed analysis with:
1. Technical requirements
2. Security assessment
3. Infrastructure considerations
4. Implementation plan

Response in Vietnamese:
"""
        confidence = 0.75
        evidence = ["Technical Documentation", "System Architecture", "Security Policies"]
        tools_used = ["document_search_tool", "web_search_tool"]
        
    else:  # GENERAL
        execution_prompt = f"""
You are a General Assistant. Provide comprehensive analysis for:

Task: {task}

Focus on:
- General research and background
- Context analysis
- Supporting information
- Coordination insights

Available tools: {', '.join(available_tools)}

Provide balanced analysis with:
1. Background research
2. Context and relevance
3. Supporting information
4. General recommendations

Response in Vietnamese:
"""
        confidence = 0.70
        evidence = ["General Research", "Web Sources", "Context Analysis"]
        tools_used = ["web_search_tool", "document_search_tool"]
    
    # Execute with LLM
    response = await llm.ainvoke(execution_prompt)
    
    return response.content, confidence, evidence, tools_used

# ================================
# WORKFLOW GRAPH CONSTRUCTION
# ================================

def create_multi_agent_workflow() -> StateGraph:
    """
    Tạo multi-agent workflow graph theo kiến trúc đã mô tả
    """
    logger.info("🏗️ Creating multi-agent workflow...")
    
    # Create workflow
    workflow = StateGraph(MultiAgentState)
    
    # Add nodes theo luồng
    workflow.add_node("analyze_complexity", analyze_query_with_llm_orchestrator)
    workflow.add_node("delegate_tasks", delegate_tasks_intelligently)
    workflow.add_node("execute_tasks", execute_specialist_agents)
    workflow.add_node("detect_conflicts", detect_conflicts)
    workflow.add_node("resolve_conflicts", resolve_conflicts)
    workflow.add_node("build_consensus", build_consensus)
    workflow.add_node("finalize_response", finalize_response)
    
    # Add edges - linear flow với conditional branching
    workflow.add_edge(START, "analyze_complexity")
    workflow.add_edge("analyze_complexity", "delegate_tasks")
    workflow.add_edge("delegate_tasks", "execute_tasks")
    workflow.add_edge("execute_tasks", "detect_conflicts")
    
    # Conditional edge: conflict detection → resolution or consensus
    def should_resolve_conflicts(state: MultiAgentState) -> Literal["resolve_conflicts", "build_consensus"]:
        """Decide if we need conflict resolution"""
        return "resolve_conflicts" if state["conflicts_detected"] else "build_consensus"
    
    workflow.add_conditional_edges(
        "detect_conflicts",
        should_resolve_conflicts,
        {
            "resolve_conflicts": "resolve_conflicts",
            "build_consensus": "build_consensus"
        }
    )
    
    workflow.add_edge("resolve_conflicts", "build_consensus")
    workflow.add_edge("build_consensus", "finalize_response")
    workflow.add_edge("finalize_response", END)
    
    return workflow

# Export compiled workflow
multi_agent_graph = create_multi_agent_workflow().compile() 