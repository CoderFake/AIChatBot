from typing import Literal, Dict, Any
from ..state.unified_state import RAGWorkflowState, ProcessingStatus, QueryDomain
from config.settings import get_settings
from utils.logging import get_logger

logger = get_logger(__name__)

class ConditionalEdges:
    """Conditional edges cho workflow routing"""
    
    @staticmethod
    def route_after_analysis(state: RAGWorkflowState) -> Literal["permission_check", "failed"]:
        """Route sau query analysis"""
        if state.get("processing_status") == ProcessingStatus.FAILED:
            return "failed"
        return "permission_check"
    
    @staticmethod 
    def route_after_permission(state: RAGWorkflowState) -> Literal["tool_selection", "permission_denied", "failed"]:
        """Route sau permission check"""
        status = state.get("processing_status")
        
        if status == ProcessingStatus.PERMISSION_DENIED:
            return "permission_denied"
        elif status == ProcessingStatus.FAILED:
            return "failed"
        else:
            return "tool_selection"
    
    @staticmethod
    def route_after_retrieval(state: RAGWorkflowState) -> Literal["synthesis", "failed"]:
        """Route sau document retrieval"""
        if state.get("processing_status") == ProcessingStatus.FAILED:
            return "failed"
        return "synthesis"
    
    @staticmethod
    def route_after_quality_check(state: RAGWorkflowState) -> Literal["finalization", "retry", "failed"]:
        """Route sau quality check"""
        settings = get_settings()
        
        quality_checks = state.get("quality_checks", {})
        retry_count = state.get("retry_count", 0)
        max_retries = settings.workflow.get("max_retries", 2)
        
        if quality_checks.get("passed", False):
            return "finalization"
        elif retry_count < max_retries:
            return "retry"
        else:
            return "failed"
    
    @staticmethod
    def should_use_tools(state: RAGWorkflowState) -> Literal["execute_tools", "retrieval"]:
        """Decide whether to use tools"""
        settings = get_settings()
        
        enabled_tools = settings.get_enabled_tools()
        complexity = state.get("query_complexity", 0.0)
        
        # Use tools for complex queries if available
        if enabled_tools and complexity > 0.6:
            return "execute_tools"
        else:
            return "retrieval"


class PermissionRouter:
    """Router for permission-based routing"""
    
    @staticmethod
    def route_by_access_level(state: RAGWorkflowState) -> Literal["high_security", "standard", "basic"]:
        """Route based on user access level"""
        max_access = state.get("max_access_level", "public")
        
        if hasattr(max_access, 'value'):
            level = max_access.value
        else:
            level = str(max_access)
        
        if level in ["restricted", "confidential"]:
            return "high_security"
        elif level == "internal":
            return "standard"
        else:
            return "basic"


class ComplexityRouter:
    """Router for complexity-based routing"""
    
    @staticmethod
    def route_by_complexity(state: RAGWorkflowState) -> Literal["simple", "moderate", "complex"]:
        """Route based on query complexity"""
        complexity = state.get("query_complexity", 0.0)
        
        if complexity < 0.3:
            return "simple"
        elif complexity < 0.7:
            return "moderate"
        else:
            return "complex"


class DomainRouter:
    """Router for domain-based routing"""
    
    @staticmethod
    def route_by_domain(state: RAGWorkflowState) -> Literal["hr", "finance", "it", "general", "cross_department"]:
        """Route based on query domain"""
        domains = state.get("domain_classification", [])
        
        if not domains:
            return "general"
        
        # Check for cross-department
        if QueryDomain.CROSS_DEPARTMENT in domains or len(domains) > 1:
            return "cross_department"
        
        # Route to primary domain
        primary_domain = domains[0]
        if hasattr(primary_domain, 'value'):
            return primary_domain.value
        else:
            return "general"


class QualityRouter:
    """Router for quality-based decisions"""
    
    @staticmethod
    def route_by_quality(state: RAGWorkflowState) -> Literal["pass", "retry", "escalate"]:
        """Route based on quality metrics"""
        quality_metrics = state.get("quality_metrics", {})
        retry_count = state.get("retry_count", 0)
        
        if not quality_metrics:
            return "escalate"
        
        overall_quality = sum(quality_metrics.values()) / len(quality_metrics)
        
        if overall_quality >= 0.8:
            return "pass"
        elif retry_count < 2:
            return "retry"
        else:
            return "escalate"
