from typing import Dict, List, Any, Optional, Union
from datetime import datetime
import json
from dataclasses import dataclass
from enum import Enum

from services.llm.provider_manager import llm_provider_manager
from config.settings import get_settings
from utils.logging import get_logger

logger = get_logger(__name__)
settings = get_settings()

class AgentDomain(Enum):
    """Domain chuyên môn của các agents"""
    HR = "hr"
    FINANCE = "finance" 
    IT = "it"
    GENERAL = "general"
    MULTI_DOMAIN = "multi_domain"

@dataclass
class AgentSelectionResult:
    """Kết quả từ orchestrator LLM"""
    selected_agents: List[AgentDomain]
    complexity_score: float
    reasoning: str
    confidence: float
    is_cross_domain: bool
    priority_order: List[str]
    estimated_execution_time: int  # seconds

class IntelligentAgentOrchestrator:
    """
    🧠 Intelligent Agent Orchestrator sử dụng LLM
    
    Thay vì hardcode keywords, sử dụng LLM để:
    - Phân tích semantic của query
    - Xác định domain expertise cần thiết
    - Quyết định agents nào tham gia
    - Đánh giá độ phức tạp và priority
    """
    
    def __init__(self):
        self.available_agents = self._get_available_agents()
        self.agent_capabilities = self._define_agent_capabilities()
        
    def _get_available_agents(self) -> Dict[str, bool]:
        """Lấy danh sách agents được admin enable"""
        return getattr(settings, 'ENABLED_AGENTS', {
            "hr_specialist": True,
            "finance_specialist": True,
            "it_specialist": True, 
            "general_assistant": True
        })
    
    def _define_agent_capabilities(self) -> Dict[str, Dict[str, Any]]:
        """Define capabilities cho từng agent (config từ admin)"""
        return {
            "hr_specialist": {
                "expertise": [
                    "Human resources policies and procedures",
                    "Employee compensation and benefits",
                    "Workplace regulations and compliance", 
                    "Performance management systems",
                    "Training and development programs",
                    "Employee relations and conflict resolution",
                    "Recruitment and onboarding processes",
                    "Leave and attendance policies"
                ],
                "tools": ["document_search_tool", "web_search_tool"],
                "languages": ["vi", "en", "ja", "ko"],
                "confidence_threshold": 0.7
            },
            "finance_specialist": {
                "expertise": [
                    "Financial analysis and reporting",
                    "Budget planning and management",
                    "Cost analysis and optimization",
                    "Investment evaluation",
                    "Tax regulations and compliance",
                    "Audit procedures and controls",
                    "Revenue recognition and accounting",
                    "Cash flow management"
                ],
                "tools": ["document_search_tool", "calculation_tool", "web_search_tool"],
                "languages": ["vi", "en", "ja", "ko"],
                "confidence_threshold": 0.7
            },
            "it_specialist": {
                "expertise": [
                    "Technology infrastructure and systems",
                    "Software development and deployment",
                    "Network security and cybersecurity",
                    "Database management and optimization",
                    "Cloud computing and DevOps",
                    "IT support and troubleshooting",
                    "Digital transformation initiatives",
                    "Technology procurement and vendor management"
                ],
                "tools": ["document_search_tool", "web_search_tool", "code_generation_tool"],
                "languages": ["vi", "en", "ja", "ko"],
                "confidence_threshold": 0.7
            },
            "general_assistant": {
                "expertise": [
                    "General information and research",
                    "Customer service and support",
                    "Administrative tasks and coordination",
                    "Multi-domain knowledge synthesis",
                    "Communication and documentation",
                    "Project coordination and follow-up"
                ],
                "tools": ["web_search_tool", "document_search_tool", "translation_tool"],
                "languages": ["vi", "en", "ja", "ko"],
                "confidence_threshold": 0.5
            }
        }
    
    async def analyze_and_select_agents(
        self,
        query: str,
        language: str = "vi",
        context: Optional[Dict[str, Any]] = None
    ) -> AgentSelectionResult:
        """
        Core method: Phân tích query và select agents bằng LLM
        
        Args:
            query: User query cần phân tích
            language: Ngôn ngữ của query  
            context: Context bổ sung từ conversation
            
        Returns:
            AgentSelectionResult với agents được chọn
        """
        logger.info(f"Orchestrating agent selection for query: {query[:100]}...")
        
        try:
            # 1. Get enabled LLM provider
            llm = await self._get_orchestrator_llm()
            
            # 2. Tạo analysis prompt cho LLM
            analysis_prompt = await self._create_orchestrator_prompt(
                query, language, context
            )
            
            # 3. LLM phân tích và select agents
            llm_response = await llm.ainvoke(analysis_prompt)
            
            # 4. Parse kết quả từ LLM
            selection_result = await self._parse_llm_response(
                llm_response.content, query, language
            )
            
            # 5. Validate và adjust selection
            validated_result = await self._validate_agent_selection(selection_result)
            
            logger.info(f"Selected agents: {[agent.value for agent in validated_result.selected_agents]} "
                       f"(confidence: {validated_result.confidence:.2f})")
            
            return validated_result
            
        except Exception as e:
            logger.error(f"Orchestrator selection failed: {e}")
            return await self._get_fallback_selection(query, language)
    
    async def _get_orchestrator_llm(self):
        """Get LLM instance cho orchestrator"""
        orchestrator_model = getattr(settings, 'ORCHESTRATOR_MODEL', 'gemini-2.0-flash')
        
        enabled_providers = getattr(settings, 'enabled_providers', [])
        if not enabled_providers:
            raise ValueError("No LLM providers enabled for orchestrator")
            
        primary_provider = enabled_providers[0]
        return await llm_provider_manager.get_provider(primary_provider)
    
    async def _create_orchestrator_prompt(
        self,
        query: str, 
        language: str,
        context: Optional[Dict[str, Any]]
    ) -> str:
        """Tạo sophisticated prompt cho LLM orchestrator"""
        
        agents_desc = []
        for agent_name, capabilities in self.agent_capabilities.items():
            if self.available_agents.get(agent_name, False):
                expertise_list = "\n    - ".join(capabilities["expertise"])
                agents_desc.append(f"""
{agent_name.upper()}:
    Expertise areas:
    - {expertise_list}
    Available tools: {', '.join(capabilities['tools'])}
""")
        
        available_agents_text = "\n".join(agents_desc)
        
        # Context information
        context_info = ""
        if context:
            context_info = f"""
Additional context:
- Previous conversation: {context.get('conversation_summary', 'None')}
- User preferences: {context.get('user_preferences', 'None')}
- Session history: {context.get('session_context', 'None')}
"""
        
        prompt_templates = {
            "vi": f"""Bạn là AI Orchestrator chuyên nghiệp, nhiệm vụ phân tích query và chọn agents phù hợp.

NHIỆM VỤ: Phân tích query sau và quyết định agents nào cần tham gia:

Query người dùng: "{query}"
Ngôn ngữ: {language}
{context_info}

CÁC AGENTS KHẢ DỤNG:
{available_agents_text}

PHÂN TÍCH YÊU CẦU:
1. Xác định domain expertise cần thiết
2. Đánh giá độ phức tạp (0.0-1.0)
3. Quyết định single-agent hay multi-agent
4. Ước tính thời gian xử lý

NGUYÊN TẮC QUAN TRỌNG:
- ƯU TIÊN single-agent nếu có thể (hiệu quả hơn)
- Chỉ dùng multi-agent khi thực sự cần cross-domain
- General assistant là fallback an toàn
- Confidence thấp = chọn general assistant

TRẢ VỀ JSON ĐỊNH DẠNG:
{{
    "selected_agents": ["hr_specialist"],
    "complexity_score": 0.6,
    "reasoning": "Query về policy lương cần chuyên gia HR",
    "confidence": 0.85,
    "is_cross_domain": false,
    "priority_order": ["hr_specialist"],
    "estimated_execution_time": 15
}}

Phân tích và quyết định:""",

            "en": f"""You are a professional AI Orchestrator. Analyze the query and select appropriate agents.

TASK: Analyze the following query and decide which agents should participate:

User query: "{query}"
Language: {language}
{context_info}

AVAILABLE AGENTS:
{available_agents_text}

ANALYSIS REQUIREMENTS:
1. Identify required domain expertise
2. Assess complexity (0.0-1.0)
3. Decide single-agent vs multi-agent
4. Estimate processing time

IMPORTANT PRINCIPLES:
- PREFER single-agent when possible (more efficient)
- Use multi-agent only when truly cross-domain
- General assistant is safe fallback
- Low confidence = choose general assistant

RETURN JSON FORMAT:
{{
    "selected_agents": ["hr_specialist"],
    "complexity_score": 0.6,
    "reasoning": "Query about salary policy needs HR expertise",
    "confidence": 0.85,
    "is_cross_domain": false,
    "priority_order": ["hr_specialist"],
    "estimated_execution_time": 15
}}

Analysis and decision:"""
        }
        
        return prompt_templates.get(language, prompt_templates["en"])
    
    async def _parse_llm_response(
        self,
        llm_response: str,
        query: str,
        language: str
    ) -> AgentSelectionResult:
        """Parse response từ LLM thành structured result"""
        
        try:
            json_start = llm_response.find('{')
            json_end = llm_response.rfind('}') + 1
            
            if json_start >= 0 and json_end > json_start:
                json_str = llm_response[json_start:json_end]
                parsed = json.loads(json_str)
                
                selected_agents = []
                for agent_name in parsed.get("selected_agents", []):
                    if "hr" in agent_name.lower():
                        selected_agents.append(AgentDomain.HR)
                    elif "finance" in agent_name.lower():
                        selected_agents.append(AgentDomain.FINANCE)
                    elif "it" in agent_name.lower():
                        selected_agents.append(AgentDomain.IT)
                    else:
                        selected_agents.append(AgentDomain.GENERAL)
                
                return AgentSelectionResult(
                    selected_agents=selected_agents or [AgentDomain.GENERAL],
                    complexity_score=max(0.0, min(1.0, parsed.get("complexity_score", 0.5))),
                    reasoning=parsed.get("reasoning", "LLM analysis completed"),
                    confidence=max(0.0, min(1.0, parsed.get("confidence", 0.7))),
                    is_cross_domain=parsed.get("is_cross_domain", False),
                    priority_order=parsed.get("priority_order", []),
                    estimated_execution_time=max(5, parsed.get("estimated_execution_time", 30))
                )
                
        except Exception as e:
            logger.warning(f"Failed to parse LLM response: {e}")
            
        return await self._get_fallback_selection(query, language)
    
    async def _validate_agent_selection(
        self, 
        selection: AgentSelectionResult
    ) -> AgentSelectionResult:
        """Validate và adjust agent selection"""
        
        valid_agents = []
        for agent in selection.selected_agents:
            agent_key = f"{agent.value}_specialist" if agent != AgentDomain.GENERAL else "general_assistant"
            
            if self.available_agents.get(agent_key, False):
                valid_agents.append(agent)
        
        if not valid_agents:
            valid_agents = [AgentDomain.GENERAL]
            selection.confidence *= 0.5
            selection.reasoning += " (Fallback to general assistant due to agent availability)"
        
        if len(valid_agents) == 1 and selection.complexity_score > 0.8:
            selection.complexity_score = 0.8 
        
        selection.selected_agents = valid_agents
        
        return selection
    
    async def _get_fallback_selection(
        self, 
        query: str, 
        language: str
    ) -> AgentSelectionResult:
        """Fallback selection khi LLM fails"""
        
        logger.warning("Using fallback agent selection")
        
        return AgentSelectionResult(
            selected_agents=[AgentDomain.GENERAL],
            complexity_score=0.5,
            reasoning="Fallback selection due to orchestrator error",
            confidence=0.4,
            is_cross_domain=False,
            priority_order=["general_assistant"],
            estimated_execution_time=30
        )
    
    async def explain_selection(
        self, 
        selection: AgentSelectionResult,
        language: str = "vi"
    ) -> str:
        """Generate human-readable explanation của agent selection"""
        
        agent_names = {
            "vi": {
                AgentDomain.HR: "Chuyên gia Nhân sự",
                AgentDomain.FINANCE: "Chuyên gia Tài chính, Marketing", 
                AgentDomain.IT: "Chuyên gia Công nghệ",
                AgentDomain.GENERAL: "Trợ lý Tổng quát"
            },
            "en": {
                AgentDomain.HR: "HR Specialist",
                AgentDomain.FINANCE: "Finance Specialist, Marketing Specialist",
                AgentDomain.IT: "IT Specialist", 
                AgentDomain.GENERAL: "General Assistant"
            }
        }
        
        selected_names = [
            agent_names.get(language, agent_names["en"])[agent] 
            for agent in selection.selected_agents
        ]
        
        templates = {
            "vi": f"""
🎯 Phân tích Agent Selection:
- Agents được chọn: {', '.join(selected_names)}
- Độ phức tạp: {selection.complexity_score:.1f}/1.0
- Confidence: {selection.confidence:.1f}/1.0
- Cross-domain: {'Có' if selection.is_cross_domain else 'Không'}
- Thời gian ước tính: {selection.estimated_execution_time}s

💭 Lý do: {selection.reasoning}
""",
            "en": f"""
🎯 Agent Selection Analysis:
- Selected agents: {', '.join(selected_names)}
- Complexity: {selection.complexity_score:.1f}/1.0
- Confidence: {selection.confidence:.1f}/1.0
- Cross-domain: {'Yes' if selection.is_cross_domain else 'No'}
- Estimated time: {selection.estimated_execution_time}s

💭 Reasoning: {selection.reasoning}
"""
        }
        
        return templates.get(language, templates["en"]) 