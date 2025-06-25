from typing import Dict, List, Any, Optional
from datetime import datetime
from dataclasses import dataclass

from langchain_core.messages import BaseMessage, AIMessage, SystemMessage
from langchain_core.tools import tool
from langgraph.prebuilt import ToolNode

from agents.base.agent_state import AgentRole, AgentResponse
from services.llm.provider_manager import llm_provider_manager
from services.tools.tool_manager import get_available_tools
from config.settings import get_settings
from utils.logging import get_logger

logger = get_logger(__name__)
settings = get_settings()

class HRSpecialistAgent:
    """
    🧑‍💼 HR Specialist Agent
    
    Chuyên gia về:
    - HR policies và regulations
    - Employee benefits và compensation  
    - Workplace policies
    - Training và development
    - Performance management
    """
    
    def __init__(self):
        self.agent_role = AgentRole.HR_SPECIALIST
        self.specialties = [
            "hr_policies",
            "employee_benefits", 
            "compensation",
            "workplace_regulations",
            "training_programs",
            "performance_management",
            "remote_work_policies",
            "leave_policies"
        ]
        
    async def execute_task(
        self,
        task: str,
        context: Dict[str, Any],
        enabled_tools: List[str]
    ) -> AgentResponse:
        """
        Thực hiện nhiệm vụ HR specialist
        
        Args:
            task: Nhiệm vụ cụ thể
            context: Context từ workflow 
            enabled_tools: Tools được admin cho phép
            
        Returns:
            AgentResponse với kết quả
        """
        start_time = datetime.now()
        
        try:
            logger.info(f"🧑‍💼 HR Agent executing: {task}")
            
            # 1. Phân tích task để xác định approach
            task_analysis = await self._analyze_hr_task(task)
            
            # 2. Tìm kiếm thông tin từ documents
            document_evidence = []
            tools_used = []
            
            if "document_search_tool" in enabled_tools:
                doc_results = await self._search_hr_documents(task, task_analysis)
                document_evidence.extend(doc_results["evidence"])
                tools_used.append("document_search_tool")
                
            # 3. Tìm kiếm web nếu cần thông tin mới
            web_evidence = []
            if "web_search_tool" in enabled_tools and task_analysis.get("needs_current_info", False):
                web_results = await self._search_hr_web_info(task)
                web_evidence.extend(web_results["evidence"])
                tools_used.append("web_search_tool")
            
            # 4. Tổng hợp và phân tích
            response_content = await self._synthesize_hr_response(
                task, document_evidence, web_evidence, task_analysis
            )
            
            # 5. Đánh giá confidence
            confidence = self._calculate_confidence(
                document_evidence, web_evidence, task_analysis
            )
            
            execution_time = (datetime.now() - start_time).total_seconds()
            
            return AgentResponse(
                agent_role=self.agent_role,
                content=response_content,
                confidence=confidence,
                evidence=document_evidence + web_evidence,
                tools_used=tools_used,
                execution_time=execution_time,
                timestamp=datetime.now()
            )
            
        except Exception as e:
            logger.error(f"HR Agent execution failed: {e}")
            execution_time = (datetime.now() - start_time).total_seconds()
            
            return AgentResponse(
                agent_role=self.agent_role,
                content=f"Lỗi khi xử lý yêu cầu HR: {str(e)}",
                confidence=0.1,
                evidence=[],
                tools_used=[],
                execution_time=execution_time,
                timestamp=datetime.now()
            )
    
    async def _analyze_hr_task(self, task: str) -> Dict[str, Any]:
        """Phân tích nhiệm vụ HR để xác định approach"""
        
        # Get enabled LLM provider
        enabled_providers = getattr(settings, 'ENABLED_PROVIDERS', {})
        primary_provider = None
        for provider, enabled in enabled_providers.items():
            if enabled:
                primary_provider = provider
                break
                
        if not primary_provider:
            raise ValueError("No LLM provider enabled")
            
        llm = await llm_provider_manager.get_provider(primary_provider)
        
        analysis_prompt = f"""
        Bạn là chuyên gia HR. Phân tích nhiệm vụ sau:
        
        Task: {task}
        
        Xác định:
        1. Loại policy nào cần tìm? (compensation, benefits, remote_work, performance, etc.)
        2. Có cần thông tin current/updated không?
        3. Có liên quan đến regulations/compliance không?
        4. Difficulty level (1-5)
        
        Trả về JSON:
        {{
            "policy_type": "remote_work",
            "needs_current_info": false,
            "involves_compliance": true,
            "difficulty": 3,
            "key_terms": ["remote work", "work from home", "policy"],
            "expected_sources": ["employee_handbook", "hr_policies", "company_regulations"]
        }}
        """
        
        response = await llm.ainvoke(analysis_prompt)
        
        try:
            import json
            return json.loads(response.content)
        except:
            # Fallback analysis
            return {
                "policy_type": "general",
                "needs_current_info": False,
                "involves_compliance": False,
                "difficulty": 2,
                "key_terms": task.lower().split(),
                "expected_sources": ["employee_handbook"]
            }
    
    async def _search_hr_documents(
        self, 
        task: str, 
        analysis: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Tìm kiếm trong HR documents"""
        
        # Get available tools
        available_tools = get_available_tools()
        
        if not available_tools.get("document_search_tool"):
            return {"evidence": [], "results": []}
            
        try:
            # Use document search tool
            search_query = f"HR {analysis.get('policy_type', '')} {task}"
            
            # Call document search tool (simulation)
            # In real implementation, this would call the actual tool
            doc_results = await self._simulate_document_search(search_query, analysis)
            
            return {
                "evidence": doc_results.get("sources", []),
                "results": doc_results.get("content", [])
            }
            
        except Exception as e:
            logger.error(f"Document search failed: {e}")
            return {"evidence": [], "results": []}
    
    async def _search_hr_web_info(self, task: str) -> Dict[str, Any]:
        """Tìm kiếm thông tin HR trên web"""
        
        available_tools = get_available_tools()
        
        if not available_tools.get("web_search_tool"):
            return {"evidence": [], "results": []}
            
        try:
            # Use web search for current HR trends/info
            search_query = f"latest HR policies Vietnam {task}"
            
            # Call web search tool (simulation)
            web_results = await self._simulate_web_search(search_query)
            
            return {
                "evidence": web_results.get("sources", []),
                "results": web_results.get("content", [])
            }
            
        except Exception as e:
            logger.error(f"Web search failed: {e}")
            return {"evidence": [], "results": []}
    
    async def _synthesize_hr_response(
        self,
        task: str,
        document_evidence: List[str],
        web_evidence: List[str],
        analysis: Dict[str, Any]
    ) -> str:
        """Tổng hợp response từ HR perspective"""
        
        # Get LLM for synthesis
        enabled_providers = getattr(settings, 'ENABLED_PROVIDERS', {})
        primary_provider = None
        for provider, enabled in enabled_providers.items():
            if enabled:
                primary_provider = provider
                break
                
        llm = await llm_provider_manager.get_provider(primary_provider)
        
        synthesis_prompt = f"""
        Bạn là HR Specialist. Dựa trên thông tin sau, trả lời câu hỏi:
        
        Question: {task}
        
        Document Evidence:
        {chr(10).join(document_evidence) if document_evidence else "Không có document evidence"}
        
        Web Evidence:
        {chr(10).join(web_evidence) if web_evidence else "Không có web evidence"}
        
        Task Analysis:
        Policy Type: {analysis.get('policy_type', 'unknown')}
        Compliance Required: {analysis.get('involves_compliance', False)}
        
        Hãy trả lời với:
        1. Thông tin chính xác từ policies
        2. Compliance requirements nếu có
        3. Practical guidance cho employee
        4. References đến sources
        
        Trả lời bằng tiếng Việt, professional và helpful.
        """
        
        response = await llm.ainvoke(synthesis_prompt)
        return response.content
    
    def _calculate_confidence(
        self,
        document_evidence: List[str],
        web_evidence: List[str], 
        analysis: Dict[str, Any]
    ) -> float:
        """Tính confidence score cho HR response"""
        
        confidence = 0.5  # Base confidence
        
        # Boost confidence based on evidence
        if document_evidence:
            confidence += 0.3  # Strong internal documents
            
        if web_evidence and analysis.get("needs_current_info"):
            confidence += 0.1  # Additional web info when needed
            
        # Adjust based on task difficulty
        difficulty = analysis.get("difficulty", 3)
        confidence -= (difficulty - 3) * 0.05
        
        # Ensure confidence is in valid range
        return max(0.1, min(1.0, confidence))
    
    async def _simulate_document_search(
        self, 
        query: str, 
        analysis: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Simulate document search (placeholder for real implementation)"""
        
        # This would be replaced with actual document search tool call
        policy_type = analysis.get("policy_type", "general")
        
        simulated_results = {
            "remote_work": {
                "sources": ["Employee Handbook v3.2", "Remote Work Policy 2024"],
                "content": ["Remote work is allowed up to 3 days per week", "Approval required from direct manager"]
            },
            "compensation": {
                "sources": ["Compensation Guidelines", "Salary Structure 2024"],
                "content": ["Salary reviews conducted annually", "Performance bonuses available"]
            },
            "benefits": {
                "sources": ["Benefits Package Overview", "Health Insurance Policy"],
                "content": ["Full health coverage provided", "Additional wellness benefits available"]
            }
        }
        
        return simulated_results.get(policy_type, {
            "sources": ["General HR Documents"],
            "content": ["Standard HR policy information available"]
        })
    
    async def _simulate_web_search(self, query: str) -> Dict[str, Any]:
        """Simulate web search (placeholder for real implementation)"""
        
        return {
            "sources": ["HR News Vietnam", "Labour Law Updates"],
            "content": ["Latest HR trends in Vietnam", "Recent policy changes"]
        }
    
    def get_specialties(self) -> List[str]:
        """Return list of HR specialties"""
        return self.specialties
    
    def can_handle_task(self, task: str) -> bool:
        """Check if this agent can handle the task"""
        task_lower = task.lower()
        hr_keywords = [
            "hr", "human resource", "nhân sự",
            "policy", "chính sách", "quy định",
            "lương", "salary", "compensation", "thưởng",
            "benefit", "phúc lợi", "bảo hiểm",
            "remote", "work from home", "làm việc từ xa",
            "training", "đào tạo", "phát triển",
            "performance", "đánh giá", "kpi",
            "leave", "nghỉ phép", "vacation"
        ]
        
        return any(keyword in task_lower for keyword in hr_keywords)
