"""
Agent Registry
Định nghĩa default agents trong hệ thống
"""
from typing import Dict, Any, List


class AgentRegistry:
    """Registry chứa definitions của default agents"""
    
    def __init__(self):
        self._initialized = False
        self._agent_definitions = {}
    
    def _ensure_initialized(self):
        """Lazy initialization"""
        if not self._initialized:
            self._agent_definitions = self._initialize_agent_definitions()
            self._initialized = True
    
    def _initialize_agent_definitions(self) -> Dict[str, Dict[str, Any]]:
        """Define default agents"""
        return {
            "hr_specialist": {
                "display_name": "HR Specialist",
                "description": "Chuyên gia nhân sự và chính sách lao động",
                "domain": "hr",
                "capabilities": [
                    "policy_analysis", "compensation_queries", "employee_benefits",
                    "workplace_regulations", "performance_management"
                ],
                "default_provider": "gemini",
                "default_model": "gemini-2.0-flash",
                "confidence_threshold": 0.75,
                "default_tools": ["document_search", "web_search"]
            },
            
            "finance_specialist": {
                "display_name": "Finance Specialist",
                "description": "Chuyên gia tài chính và kế toán",
                "domain": "finance",
                "capabilities": [
                    "financial_analysis", "budget_planning", "cost_analysis",
                    "tax_regulations", "audit_procedures"
                ],
                "default_provider": "ollama",
                "default_model": "llama3.1:8b",
                "confidence_threshold": 0.75,
                "default_tools": ["document_search", "calculation", "web_search", "statistics"]
            },
            
            "it_specialist": {
                "display_name": "IT Specialist",
                "description": "Chuyên gia công nghệ thông tin",
                "domain": "it",
                "capabilities": [
                    "infrastructure_analysis", "security_assessment", "software_development",
                    "system_troubleshooting", "technology_planning"
                ],
                "default_provider": "mistral",
                "default_model": "mistral-large-latest",
                "confidence_threshold": 0.70,
                "default_tools": ["document_search", "web_search", "file_read", "json_parse"]
            },
            
            "general_assistant": {
                "display_name": "General Assistant",
                "description": "Trợ lý đa năng",
                "domain": "general",
                "capabilities": [
                    "general_research", "information_synthesis", "communication_support",
                    "task_coordination", "multi_domain_analysis"
                ],
                "default_provider": "gemini",
                "default_model": "gemini-2.0-flash",
                "confidence_threshold": 0.60,
                "default_tools": ["web_search", "document_search", "datetime", "weather"]
            }
        }
    
    def get_all_agents(self) -> Dict[str, Dict[str, Any]]:
        """Lấy tất cả agent definitions"""
        self._ensure_initialized()
        return self._agent_definitions.copy()
    
    def get_agent_definition(self, agent_name: str) -> Dict[str, Any]:
        """Lấy definition của agent"""
        self._ensure_initialized()
        return self._agent_definitions.get(agent_name, {})
    
    def get_agents_by_domain(self, domain: str) -> Dict[str, Dict[str, Any]]:
        """Lấy agents theo domain"""
        self._ensure_initialized()
        return {
            name: definition for name, definition in self._agent_definitions.items()
            if definition.get("domain") == domain
        }


# Global instance
agent_registry = AgentRegistry() 