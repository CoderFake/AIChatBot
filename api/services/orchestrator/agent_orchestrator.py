from typing import Dict, List, Any, Optional, Union
from datetime import datetime
import asyncio
from dataclasses import dataclass
from enum import Enum

from config.settings import get_settings
from services.llm.provider_manager import llm_provider_manager
from utils.logging import get_logger

logger = get_logger(__name__)
settings = get_settings()

class AgentDomain(Enum):
    """Agent domains từ configuration"""
    HR = "hr"
    FINANCE = "finance" 
    IT = "it"
    GENERAL = "general"

@dataclass
class AgentSelectionResult:
    """Kết quả từ orchestrator LLM"""
    selected_agents: List[str]
    complexity_score: float
    reasoning: str
    confidence: float
    is_cross_domain: bool
    priority_order: List[str]
    estimated_execution_time: int

class IntelligentAgentOrchestrator:
    """
    Intelligent Agent Orchestrator sử dụng LLM
    Configuration-driven, loại bỏ hardcode keywords
    """
    
    def __init__(self):
        self.settings = get_settings()
        self.available_agents = self._get_available_agents()
        self.agent_capabilities = self._load_agent_capabilities()
        
    def _get_available_agents(self) -> Dict[str, bool]:
        """Lấy danh sách agents được enable từ config"""
        return {
            agent_name: config.get('enabled', False) 
            for agent_name, config in self.settings.agents.items()
        }
    
    def _load_agent_capabilities(self) -> Dict[str, Dict[str, Any]]:
        """Load capabilities từ configuration thay vì hardcode"""
        capabilities = {}
        
        for agent_name, config in self.settings.agents.items():
            if config.get('enabled', False):
                capabilities[agent_name] = {
                    'domain': config.get('domain', 'general'),
                    'capabilities': config.get('capabilities', []),
                    'tools': config.get('tools', []),
                    'model': config.get('model', 'gemini-2.0-flash'),
                    'provider': config.get('provider', 'gemini'),
                    'confidence_threshold': config.get('confidence_threshold', 0.7)
                }
        
        return capabilities
    
    async def analyze_and_select_agents(
        self,
        query: str,
        language: str = "vi",
        context: Optional[Dict[str, Any]] = None
    ) -> AgentSelectionResult:
        """
        Core method: Phân tích query và select agents bằng LLM
        """
        logger.info(f"Orchestrating agent selection for query: {query[:100]}...")
        
        try:
            llm = await self._get_orchestrator_llm()
            
            analysis_prompt = await self._create_orchestrator_prompt(
                query, language, context
            )
            
            llm_response = await llm.ainvoke(analysis_prompt)
            
            selection_result = await self._parse_llm_response(
                llm_response.content, query, language
            )
            
            validated_result = await self._validate_agent_selection(selection_result)
            
            logger.info(f"Selected agents: {validated_result.selected_agents} "
                       f"(confidence: {validated_result.confidence:.2f})")
            
            return validated_result
            
        except Exception as e:
            logger.error(f"Orchestrator selection failed: {e}")
            return await self._get_fallback_selection(query, language)
    
    async def _get_orchestrator_llm(self):
        """Get LLM instance cho orchestrator"""
        orchestrator_config = self.settings.orchestrator
        model = orchestrator_config.get('model', 'gemini-2.0-flash')
        
        enabled_providers = self.settings.get_enabled_providers()
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
                capabilities_list = "\n    - ".join(capabilities["capabilities"])
                agents_desc.append(f"""
{agent_name.upper()}:
    Domain: {capabilities["domain"]}
    Capabilities:
    - {capabilities_list}
    Available tools: {', '.join(capabilities['tools'])}
    Model: {capabilities["model"]}
""")
        
        available_agents_text = "\n".join(agents_desc)
        
        context_info = ""
        if context:
            context_info = f"""
Additional context:
- Previous conversation: {context.get('conversation_summary', 'None')}
- User preferences: {context.get('user_preferences', 'None')}
- Session history: {context.get('session_context', 'None')}
"""
        
        orchestrator_settings = self.settings.orchestrator
        max_agents = orchestrator_settings.get('max_agents_per_query', 3)
        confidence_threshold = orchestrator_settings.get('confidence_threshold', 0.7)
        
        prompt_templates = {
            "vi": f"""Bạn là AI Orchestrator chuyên nghiệp, nhiệm vụ phân tích query và chọn agents phù hợp.

NHIỆM VỤ: Phân tích query sau và quyết định agents nào cần tham gia:

Query người dùng: "{query}"
Ngôn ngữ: {language}
{context_info}

CÁC AGENTS KHẢ DỤNG:
{available_agents_text}

CẤU HÌNH ORCHESTRATOR:
- Max agents per query: {max_agents}
- Confidence threshold: {confidence_threshold}

NGUYÊN TẮC QUAN TRỌNG:
- ƯU TIÊN single-agent nếu có thể (hiệu quả hơn)
- Chỉ dùng multi-agent khi thực sự cần cross-domain
- Chọn agent có domain và capabilities phù hợp nhất
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

ORCHESTRATOR CONFIGURATION:
- Max agents per query: {max_agents}
- Confidence threshold: {confidence_threshold}

IMPORTANT PRINCIPLES:
- PREFER single-agent when possible (more efficient)
- Use multi-agent only when truly cross-domain
- Choose agent with best domain and capabilities match
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
        
        return prompt_templates.get(language, prompt_templates["vi"])
    
    async def _parse_llm_response(
        self,
        llm_response: str,
        query: str,
        language: str
    ) -> AgentSelectionResult:
        """Parse response từ LLM thành structured result"""
        
        try:
            import json
            json_start = llm_response.find('{')
            json_end = llm_response.rfind('}') + 1
            
            if json_start >= 0 and json_end > json_start:
                json_str = llm_response[json_start:json_end]
                parsed = json.loads(json_str)
                
                selected_agents = parsed.get("selected_agents", [])
                
                return AgentSelectionResult(
                    selected_agents=selected_agents,
                    complexity_score=max(0.0, min(1.0, parsed.get("complexity_score", 0.5))),
                    reasoning=parsed.get("reasoning", "LLM analysis completed"),
                    confidence=max(0.0, min(1.0, parsed.get("confidence", 0.7))),
                    is_cross_domain=parsed.get("is_cross_domain", False),
                    priority_order=parsed.get("priority_order", selected_agents),
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
        for agent_name in selection.selected_agents:
            if self.available_agents.get(agent_name, False):
                valid_agents.append(agent_name)
        
        if not valid_agents:
            if self.available_agents.get("general_assistant", False):
                valid_agents = ["general_assistant"]
            else:
                # Lấy agent đầu tiên available
                for agent_name, enabled in self.available_agents.items():
                    if enabled:
                        valid_agents = [agent_name]
                        break
            
            selection.confidence *= 0.5
            selection.reasoning += " (Adjusted due to agent availability)"
        
        max_agents = self.settings.orchestrator.get('max_agents_per_query', 3)
        if len(valid_agents) > max_agents:
            valid_agents = valid_agents[:max_agents]
            selection.reasoning += f" (Limited to {max_agents} agents)"
        
        selection.selected_agents = valid_agents
        
        return selection
    
    async def _get_fallback_selection(
        self, 
        query: str, 
        language: str
    ) -> AgentSelectionResult:
        """Fallback selection khi LLM fails"""
        
        logger.warning("Using fallback agent selection")
        
        fallback_agent = "general_assistant"
        if not self.available_agents.get(fallback_agent, False):
            for agent_name, enabled in self.available_agents.items():
                if enabled:
                    fallback_agent = agent_name
                    break
        
        return AgentSelectionResult(
            selected_agents=[fallback_agent] if fallback_agent else [],
            complexity_score=0.5,
            reasoning="Fallback selection due to orchestrator error",
            confidence=0.4,
            is_cross_domain=False,
            priority_order=[fallback_agent] if fallback_agent else [],
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
                "hr_specialist": "Chuyên gia Nhân sự",
                "finance_specialist": "Chuyên gia Tài chính",
                "it_specialist": "Chuyên gia Công nghệ",
                "general_assistant": "Trợ lý Tổng quát"
            },
            "en": {
                "hr_specialist": "HR Specialist",
                "finance_specialist": "Finance Specialist",
                "it_specialist": "IT Specialist",
                "general_assistant": "General Assistant"
            }
        }
        
        selected_names = [
            agent_names.get(language, agent_names["en"]).get(agent, agent)
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

class AgentOrchestrator:
    """
    Main Agent Orchestrator class - tích hợp với existing codebase
    """
    
    def __init__(self):
        self.settings = get_settings()
        self.intelligent_orchestrator = IntelligentAgentOrchestrator()
        self.agents: Dict[str, Any] = {}
        self._initialized = False
    
    async def initialize(self):
        """Initialize orchestrator và load agents"""
        if self._initialized:
            return
        
        try:
            await self._load_agents_from_config()
            self._initialized = True
            logger.info(f"Agent Orchestrator initialized with {len(self.agents)} agents")
        except Exception as e:
            logger.error(f"Failed to initialize Agent Orchestrator: {e}")
            raise
    
    async def _load_agents_from_config(self):
        """Load agents dynamically từ configuration"""
        enabled_agents = self.settings.get_enabled_agents()
        
        for agent_name in enabled_agents:
            try:
                agent_instance = await self._create_agent_instance(agent_name)
                if agent_instance:
                    await agent_instance.initialize()
                    self.agents[agent_name] = agent_instance
                    logger.info(f"Loaded agent: {agent_name}")
            except Exception as e:
                logger.error(f"Failed to load agent {agent_name}: {e}")
    
    async def _create_agent_instance(self, agent_name: str) -> Optional[Any]:
        """Create agent instance based on name"""
        agent_config = self.settings.agents.get(agent_name)
        
        if not agent_config or not agent_config.get('enabled', False):
            logger.info(f"Agent {agent_name} is disabled")
            return None
        
        try:
            if agent_name == "hr_specialist":
                from agents.domain.hr_agent import HRSpecialistAgent
                return HRSpecialistAgent()
            elif agent_name == "finance_specialist":
                # Sẽ implement khi có file
                logger.warning(f"Finance agent not implemented yet")
                return None
            elif agent_name == "it_specialist":
                # Sẽ implement khi có file
                logger.warning(f"IT agent not implemented yet")
                return None
            elif agent_name == "general_assistant":
                # Sẽ implement khi có file
                logger.warning(f"General agent not implemented yet")
                return None
            else:
                logger.warning(f"Unknown agent type: {agent_name}")
                return None
                
        except ImportError as e:
            logger.warning(f"Agent {agent_name} not implemented yet: {e}")
            return None
    
    async def select_agents(
        self,
        query: str,
        language: str = "vi",
        complexity: float = 0.5
    ) -> Dict[str, Any]:
        """Select agents cho query"""
        if not self._initialized:
            await self.initialize()
        
        try:
            strategy = self.settings.orchestrator.get("strategy", "llm_orchestrator")
            
            if strategy == "llm_orchestrator":
                selection_result = await self.intelligent_orchestrator.analyze_and_select_agents(
                    query, language
                )
                
                return {
                    "selected_agents": selection_result.selected_agents,
                    "reasoning": selection_result.reasoning,
                    "confidence": selection_result.confidence,
                    "complexity_score": selection_result.complexity_score,
                    "method": "llm_orchestrator"
                }
            else:
                return await self._rule_based_selection(query, language)
                
        except Exception as e:
            logger.error(f"Agent selection failed: {e}")
            return await self._fallback_selection(query)
    
    async def _rule_based_selection(self, query: str, language: str) -> Dict[str, Any]:
        """Rule-based agent selection fallback"""
        query_lower = query.lower()
        agent_scores = {}
        
        for agent_name, agent in self.agents.items():
            if hasattr(agent, 'can_handle_task') and agent.can_handle_task(query):
                agent_scores[agent_name] = 0.8
        
        if not agent_scores:
            selected_agents = ["general_assistant"] if "general_assistant" in self.agents else []
        else:
            max_agents = self.settings.orchestrator.get('max_agents_per_query', 3)
            sorted_agents = sorted(agent_scores.items(), key=lambda x: x[1], reverse=True)
            selected_agents = [agent for agent, score in sorted_agents[:max_agents]]
        
        return {
            "selected_agents": selected_agents,
            "reasoning": "Rule-based selection using capabilities",
            "confidence": 0.6,
            "method": "rule_based"
        }
    
    async def _fallback_selection(self, query: str) -> Dict[str, Any]:
        """Fallback selection"""
        if "general_assistant" in self.agents:
            selected = ["general_assistant"]
        elif self.agents:
            selected = [next(iter(self.agents.keys()))]
        else:
            selected = []
        
        return {
            "selected_agents": selected,
            "reasoning": "Fallback selection due to errors",
            "confidence": 0.3,
            "method": "fallback"
        }
    
    async def execute_agent_task(
        self,
        agent_name: str,
        task: str,
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Execute task cho specific agent"""
        if agent_name not in self.agents:
            logger.error(f"Agent {agent_name} not available")
            return {
                "success": False,
                "error": f"Agent {agent_name} not found",
                "response": f"Agent {agent_name} không khả dụng"
            }
        
        try:
            agent = self.agents[agent_name]
            
            if hasattr(agent, 'enabled_tools'):
                enabled_tools = agent.enabled_tools
            else:
                enabled_tools = []
            
            result = await agent.execute_task(task, context, enabled_tools)
            
            return {
                "success": result.success if hasattr(result, 'success') else True,
                "response": result.content if hasattr(result, 'content') else str(result),
                "confidence": result.confidence if hasattr(result, 'confidence') else 0.7,
                "evidence": result.evidence if hasattr(result, 'evidence') else [],
                "tools_used": result.tools_used if hasattr(result, 'tools_used') else [],
                "reasoning": result.reasoning if hasattr(result, 'reasoning') else ""
            }
            
        except Exception as e:
            logger.error(f"Agent {agent_name} execution failed: {e}")
            return {
                "success": False,
                "error": str(e),
                "response": f"Lỗi khi thực thi agent {agent_name}: {str(e)}"
            }