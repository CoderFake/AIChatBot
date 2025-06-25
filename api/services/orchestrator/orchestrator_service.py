from typing import Dict, List, Any, Optional, Union
from datetime import datetime
import asyncio

from services.orchestrator.agent_orchestrator import (
    IntelligentAgentOrchestrator, 
    AgentSelectionResult,
    AgentDomain
)
from agents.domain.hr_agent import HRSpecialistAgent
from config.settings import get_settings
from utils.logging import get_logger

logger = get_logger(__name__)
settings = get_settings()

class OrchestratorService:
    """
    🎯 Service để integrate Intelligent Orchestrator vào main workflow
    
    Thay thế keyword-based routing bằng LLM-based agent selection
    """
    
    def __init__(self):
        self.orchestrator = IntelligentAgentOrchestrator()
        self.agents = self._initialize_agents()
        
    def _initialize_agents(self) -> Dict[str, Any]:
        """Initialize available agents"""
        agents = {}
        
        # Get enabled agents from admin
        enabled_agents = getattr(settings, 'ENABLED_AGENTS', {})
        
        if enabled_agents.get('hr_specialist', False):
            agents['hr_specialist'] = HRSpecialistAgent()
            
        # Initialize other agents when available
        # if enabled_agents.get('finance_specialist', False):
        #     agents['finance_specialist'] = FinanceSpecialistAgent()
        #     
        # if enabled_agents.get('it_specialist', False):
        #     agents['it_specialist'] = ITSpecialistAgent()
            
        logger.info(f"🎯 Initialized {len(agents)} specialist agents")
        return agents
    
    async def orchestrate_query(
        self,
        query: str,
        language: str = "vi",
        user_context: Optional[Dict[str, Any]] = None,
        session_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        🧠 Main orchestration method
        
        Args:
            query: User query
            language: Language code
            user_context: User context and preferences
            session_id: Session identifier
            
        Returns:
            Orchestrated response với agent selection và execution
        """
        start_time = datetime.now()
        
        logger.info(f"🎯 Orchestrating query: {query[:100]}...")
        
        try:
            # 1. LLM Orchestrator phân tích và select agents
            selection_result = await self.orchestrator.analyze_and_select_agents(
                query=query,
                language=language,
                context=user_context or {}
            )
            
            # 2. Check agent selection strategy từ admin
            strategy = getattr(settings, 'AGENT_SELECTION_STRATEGY', 'llm_orchestrator')
            
            if strategy == "keyword_matching":
                # Fallback to keyword-based selection
                logger.info("🔄 Using keyword-based selection (admin override)")
                return await self._execute_keyword_based_routing(query, language, user_context)
                
            elif strategy == "hybrid":
                # Combine LLM và keyword approaches
                logger.info("🔄 Using hybrid selection strategy")
                return await self._execute_hybrid_routing(
                    query, language, user_context, selection_result
                )
            
            # 3. Default: LLM orchestrator strategy
            return await self._execute_llm_orchestrated_workflow(
                query, language, user_context, selection_result, start_time
            )
            
        except Exception as e:
            logger.error(f"❌ Orchestration failed: {e}")
            return await self._get_fallback_response(query, language, user_context, str(e))
    
    async def _execute_llm_orchestrated_workflow(
        self,
        query: str,
        language: str,
        user_context: Optional[Dict[str, Any]],
        selection_result: AgentSelectionResult,
        start_time: datetime
    ) -> Dict[str, Any]:
        """Execute workflow with LLM orchestrator"""
        
        logger.info(f"🧠 Executing LLM orchestrated workflow with agents: "
                   f"{[agent.value for agent in selection_result.selected_agents]}")
        
        # 1. Prepare context for agents
        agent_context = {
            "original_query": query,
            "language": language,
            "user_context": user_context or {},
            "orchestrator_analysis": selection_result.__dict__,
            "execution_strategy": "llm_orchestrator"
        }
        
        # 2. Execute selected agents
        agent_results = await self._execute_selected_agents(
            selection_result.selected_agents, query, agent_context
        )
        
        # 3. Synthesize results
        final_response = await self._synthesize_agent_results(
            agent_results, selection_result, language
        )
        
        execution_time = (datetime.now() - start_time).total_seconds()
        
        # 4. Build orchestrated response
        return {
            "response": final_response["content"],
            "citations": final_response.get("citations", []),
            "metadata": {
                "orchestration_method": "llm_orchestrator",
                "selected_agents": [agent.value for agent in selection_result.selected_agents],
                "complexity_score": selection_result.complexity_score,
                "confidence": selection_result.confidence,
                "is_cross_domain": selection_result.is_cross_domain,
                "orchestrator_reasoning": selection_result.reasoning,
                "agent_results": agent_results,
                "execution_time": execution_time,
                "timestamp": datetime.now().isoformat()
            }
        }
    
    async def _execute_selected_agents(
        self,
        selected_agents: List[AgentDomain],
        query: str,
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Execute tasks for selected agents in parallel"""
        
        agent_results = {}
        
        # Get enabled tools từ admin
        enabled_tools = getattr(settings, 'enabled_tools', {})
        available_tools = [tool for tool, enabled in enabled_tools.items() if enabled]
        
        # Execute agents in parallel
        tasks = []
        for agent_domain in selected_agents:
            task = self._create_agent_execution_task(
                agent_domain, query, context, available_tools
            )
            tasks.append(task)
        
        # Wait for all agents to complete
        if tasks:
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Process results
            for i, result in enumerate(results):
                agent_domain = selected_agents[i]
                agent_key = f"{agent_domain.value}_specialist" if agent_domain != AgentDomain.GENERAL else "general_assistant"
                
                if isinstance(result, Exception):
                    logger.error(f"❌ {agent_key} execution failed: {result}")
                    agent_results[agent_key] = {
                        "success": False,
                        "error": str(result),
                        "response": f"Agent {agent_key} encountered an error",
                        "confidence": 0.1
                    }
                else:
                    agent_results[agent_key] = result
                    
        return agent_results
    
    async def _create_agent_execution_task(
        self,
        agent_domain: AgentDomain,
        query: str,
        context: Dict[str, Any],
        available_tools: List[str]
    ) -> Dict[str, Any]:
        """Create execution task for specific agent domain"""
        
        if agent_domain == AgentDomain.HR and 'hr_specialist' in self.agents:
            # Execute HR specialist
            hr_agent = self.agents['hr_specialist']
            
            try:
                # Create task specific for HR domain
                hr_task = f"Analyze HR policies, employee relations, and workplace matters related to: {query}"
                
                result = await hr_agent.execute_task(
                    task=hr_task,
                    context=context,
                    enabled_tools=available_tools
                )
                
                return {
                    "success": True,
                    "agent_domain": agent_domain.value,
                    "response": result.content,
                    "confidence": result.confidence,
                    "evidence": result.evidence,
                    "tools_used": result.tools_used,
                    "execution_time": result.execution_time
                }
                
            except Exception as e:
                logger.error(f"HR agent execution failed: {e}")
                return {
                    "success": False,
                    "agent_domain": agent_domain.value,
                    "error": str(e),
                    "response": f"HR analysis unavailable due to error: {str(e)}",
                    "confidence": 0.1
                }
        
        # For other domains not yet implemented
        else:
            # Simulate agent execution
            return await self._simulate_agent_execution(agent_domain, query, context)
    
    async def _simulate_agent_execution(
        self,
        agent_domain: AgentDomain,
        query: str,
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Simulate agent execution for domains not yet implemented"""
        
        # Get LLM provider for simulation
        from services.llm.provider_manager import llm_provider_manager
        
        enabled_providers = getattr(settings, 'enabled_providers', [])
        if not enabled_providers:
            raise ValueError("No LLM providers enabled")
            
        llm = await llm_provider_manager.get_provider(enabled_providers[0])
        
        # Domain-specific simulation prompts
        domain_prompts = {
            AgentDomain.FINANCE: f"""
You are a Finance Specialist. Analyze from financial perspective:

Query: {query}

Focus on:
- Budget impact and cost considerations  
- Financial compliance and regulations
- Investment and ROI analysis
- Risk assessment

Provide detailed financial analysis in Vietnamese.
""",
            AgentDomain.IT: f"""
You are an IT Specialist. Analyze from technology perspective:

Query: {query}

Focus on:
- Technical requirements and infrastructure
- System security and compliance
- Technology implementation considerations
- Digital transformation impact

Provide detailed technical analysis in Vietnamese.
""",
            AgentDomain.GENERAL: f"""
You are a General Assistant. Provide comprehensive analysis:

Query: {query}

Focus on:
- General research and background information
- Context analysis and relevance
- Supporting information from multiple perspectives
- Coordination and synthesis insights

Provide balanced general analysis in Vietnamese.
"""
        }
        
        prompt = domain_prompts.get(agent_domain, domain_prompts[AgentDomain.GENERAL])
        
        try:
            response = await llm.ainvoke(prompt)
            
            # Simulate confidence based on domain
            confidence_map = {
                AgentDomain.FINANCE: 0.75,
                AgentDomain.IT: 0.70,
                AgentDomain.GENERAL: 0.65
            }
            
            return {
                "success": True,
                "agent_domain": agent_domain.value,
                "response": response.content,
                "confidence": confidence_map.get(agent_domain, 0.6),
                "evidence": [f"{agent_domain.value.title()} Knowledge Base"],
                "tools_used": ["llm_analysis"],
                "execution_time": 2.5,
                "simulated": True
            }
            
        except Exception as e:
            logger.error(f"Simulated {agent_domain.value} agent failed: {e}")
            return {
                "success": False,
                "agent_domain": agent_domain.value,
                "error": str(e),
                "response": f"{agent_domain.value.title()} analysis unavailable",
                "confidence": 0.1
            }
    
    async def _synthesize_agent_results(
        self,
        agent_results: Dict[str, Any],
        selection_result: AgentSelectionResult,
        language: str
    ) -> Dict[str, Any]:
        """Synthesize results from multiple agents into final response"""
        
        if not agent_results:
            return {
                "content": "Không có kết quả từ các agents",
                "citations": [],
                "confidence": 0.1
            }
        
        # Single agent case
        if len(agent_results) == 1:
            agent_key = list(agent_results.keys())[0]
            result = agent_results[agent_key]
            
            return {
                "content": result.get("response", "Không có response từ agent"),
                "citations": result.get("evidence", []),
                "confidence": result.get("confidence", 0.5)
            }
        
        # Multi-agent synthesis
        return await self._synthesize_multi_agent_results(
            agent_results, selection_result, language
        )
    
    async def _synthesize_multi_agent_results(
        self,
        agent_results: Dict[str, Any],
        selection_result: AgentSelectionResult,
        language: str
    ) -> Dict[str, Any]:
        """Synthesize multiple agent results using LLM"""
        
        from services.llm.provider_manager import llm_provider_manager
        
        # Get LLM for synthesis
        enabled_providers = getattr(settings, 'enabled_providers', [])
        llm = await llm_provider_manager.get_provider(enabled_providers[0])
        
        # Prepare agent contributions
        agent_contributions = []
        all_evidence = []
        total_confidence = 0
        successful_agents = 0
        
        for agent_key, result in agent_results.items():
            if result.get("success", False):
                agent_contributions.append(f"""
**{agent_key.replace('_', ' ').title()}** (Confidence: {result.get('confidence', 0):.2f}):
{result.get('response', '')}
""")
                all_evidence.extend(result.get('evidence', []))
                total_confidence += result.get('confidence', 0)
                successful_agents += 1
        
        if successful_agents == 0:
            return {
                "content": "Tất cả các agents gặp lỗi trong quá trình xử lý",
                "citations": [],
                "confidence": 0.1
            }
        
        # Create synthesis prompt
        synthesis_prompt = f"""
Bạn là AI Synthesizer chuyên nghiệp. Hãy tổng hợp insights từ các chuyên gia sau thành một response hoàn chỉnh và chính xác.

🎯 NHIỆM VỤ TỔNG HỢP:
Query gốc: "{selection_result.reasoning}"

🧠 INSIGHTS TỪ CÁC CHUYÊN GIA:
{chr(10).join(agent_contributions)}

📊 THÔNG TIN PHÂN TÍCH:
- Độ phức tạp: {selection_result.complexity_score:.2f}
- Cross-domain: {selection_result.is_cross_domain}
- Số agents tham gia: {successful_agents}

⚡ YÊU CẦU TỔNG HỢP:
1. Kết hợp insights từ tất cả chuyên gia
2. Loại bỏ thông tin trùng lặp hoặc mâu thuẫn
3. Tạo response thống nhất và dễ hiểu
4. Ưu tiên độ chính xác và tính thực tiễn
5. Giữ nguyên language: {language}

🎯 TRẢ LỜI CUỐI CÙNG:
Tổng hợp chuyên nghiệp từ các experts:
"""
        
        # Synthesize with LLM
        try:
            synthesis_response = await llm.ainvoke(synthesis_prompt)
            
            avg_confidence = total_confidence / successful_agents
            
            return {
                "content": synthesis_response.content,
                "citations": list(set(all_evidence)),  # Remove duplicates
                "confidence": min(avg_confidence, 0.95)  # Cap at 95%
            }
            
        except Exception as e:
            logger.error(f"Synthesis failed: {e}")
            
            # Fallback: return highest confidence agent result
            best_agent = max(
                agent_results.items(),
                key=lambda x: x[1].get('confidence', 0) if x[1].get('success') else 0
            )
            
            return {
                "content": best_agent[1].get('response', 'Synthesis failed'),
                "citations": best_agent[1].get('evidence', []),
                "confidence": best_agent[1].get('confidence', 0.3)
            }
    
    async def _execute_keyword_based_routing(
        self,
        query: str,
        language: str,
        user_context: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Fallback keyword-based routing"""
        
        logger.info("🔄 Executing keyword-based routing (fallback)")
        
        # Simple keyword detection for fallback
        query_lower = query.lower()
        
        # Check HR keywords
        hr_keywords = getattr(settings, 'HR_KEYWORDS', {}).get(language, [])
        if any(keyword.lower() in query_lower for keyword in hr_keywords):
            if 'hr_specialist' in self.agents:
                hr_agent = self.agents['hr_specialist']
                result = await hr_agent.execute_task(
                    task=query,
                    context={"language": language, "user_context": user_context},
                    enabled_tools=getattr(settings, 'enabled_tools', {})
                )
                
                return {
                    "response": result.content,
                    "citations": result.evidence,
                    "metadata": {
                        "orchestration_method": "keyword_based_fallback",
                        "selected_agent": "hr_specialist",
                        "confidence": result.confidence
                    }
                }
        
        # Default fallback
        return await self._get_fallback_response(query, language, user_context, "keyword_routing_no_match")
    
    async def _execute_hybrid_routing(
        self,
        query: str,
        language: str,
        user_context: Optional[Dict[str, Any]],
        llm_selection: AgentSelectionResult
    ) -> Dict[str, Any]:
        """Hybrid routing combining LLM and keyword approaches"""
        
        logger.info("🔄 Executing hybrid routing strategy")
        
        # If LLM confidence is high, use LLM selection
        if llm_selection.confidence >= getattr(settings, 'ORCHESTRATOR_CONFIDENCE_THRESHOLD', 0.7):
            return await self._execute_llm_orchestrated_workflow(
                query, language, user_context, llm_selection, datetime.now()
            )
        
        # Otherwise, use keyword-based as backup
        return await self._execute_keyword_based_routing(query, language, user_context)
    
    async def _get_fallback_response(
        self,
        query: str,
        language: str,
        user_context: Optional[Dict[str, Any]],
        error_reason: str
    ) -> Dict[str, Any]:
        """Generate fallback response when orchestration fails"""
        
        logger.warning(f"Using fallback response due to: {error_reason}")
        
        fallback_messages = {
            "vi": "Xin lỗi, tôi gặp khó khăn trong việc phân tích câu hỏi của bạn. Vui lòng thử diễn đạt lại hoặc liên hệ với bộ phận hỗ trợ.",
            "en": "Sorry, I'm having difficulty analyzing your question. Please try rephrasing or contact support.",
            "ja": "申し訳ありませんが、ご質問の分析に困難があります。言い換えるか、サポートにお問い合わせください。",
            "ko": "죄송합니다. 질문 분석에 어려움이 있습니다. 다시 표현하거나 지원팀에 문의해 주세요."
        }
        
        return {
            "response": fallback_messages.get(language, fallback_messages["vi"]),
            "citations": [],
            "metadata": {
                "orchestration_method": "fallback",
                "error_reason": error_reason,
                "confidence": 0.3,
                "timestamp": datetime.now().isoformat()
            }
        } 