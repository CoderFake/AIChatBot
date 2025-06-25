from typing import Dict, Any, List
from datetime import datetime

from ..state.workflow_state import RAGWorkflowState, AccessLevel, ProcessingStatus
from config.settings import get_settings
from utils.logging import get_logger

logger = get_logger(__name__)

class PermissionCheckNode:
    """Kiểm tra quyền truy cập user cho query"""
    
    def __init__(self):
        self.settings = get_settings()
        
    async def process(self, state: RAGWorkflowState) -> RAGWorkflowState:
        """Kiểm tra permissions cho query và domain"""
        
        try:
            user_permissions = state.get("user_permissions", [])
            domain_classification = state.get("domain_classification", [])
            
            # Check domain permissions
            domain_access = self._check_domain_access(user_permissions, domain_classification)
            
            # Check cross-department permissions
            cross_dept_access = self._check_cross_department_access(
                state.get("requires_cross_department", False),
                user_permissions,
                state.get("user_department", "")
            )
            
            # Log permission check
            permission_check = {
                "timestamp": datetime.now(),
                "user_id": state.get("user_id", ""),
                "domains_checked": [d.value for d in domain_classification],
                "domain_access": domain_access,
                "cross_dept_access": cross_dept_access,
                "result": domain_access and cross_dept_access
            }
            
            # Update state
            permission_checks = state.get("permission_checks", [])
            permission_checks.append(permission_check)
            
            if not (domain_access and cross_dept_access):
                return {
                    **state,
                    "processing_status": ProcessingStatus.PERMISSION_DENIED,
                    "permission_checks": permission_checks,
                    "error_messages": ["Insufficient permissions for this query"]
                }
            
            return {
                **state,
                "permission_checks": permission_checks
            }
            
        except Exception as e:
            logger.error(f"Permission check failed: {e}")
            return {
                **state,
                "processing_status": ProcessingStatus.FAILED,
                "error_messages": [f"Permission check error: {str(e)}"]
            }
    
    def _check_domain_access(self, user_permissions: List[str], domains: List) -> bool:
        """Check access to specific domains"""
        required_permissions = {
            "hr": ["hr_read", "hr_access"],
            "finance": ["finance_read", "finance_access"], 
            "it": ["it_read", "it_access"],
            "general": ["general_read"]
        }
        
        for domain in domains:
            domain_name = domain.value if hasattr(domain, 'value') else str(domain)
            required_perms = required_permissions.get(domain_name, ["general_read"])
            
            if not any(perm in user_permissions for perm in required_perms):
                return False
        
        return True
    
    def _check_cross_department_access(self, requires_cross_dept: bool, user_permissions: List[str], user_dept: str) -> bool:
        """Check cross-department access permissions"""
        if not requires_cross_dept:
            return True
        
        return "cross_department_access" in user_permissions or "admin" in user_permissions


class DocumentFilterNode:
    """Filter documents dựa trên user permissions"""
    
    def __init__(self):
        self.settings = get_settings()
        
    async def process(self, state: RAGWorkflowState) -> RAGWorkflowState:
        """Filter retrieved documents theo permissions"""
        
        try:
            raw_results = state.get("raw_retrieval_results", {})
            user_permissions = state.get("user_permissions", [])
            max_access_level = state.get("max_access_level", AccessLevel.PUBLIC)
            
            filtered_results = {}
            permission_filtered_count = 0
            
            for collection, documents in raw_results.items():
                filtered_docs = []
                
                for doc in documents:
                    if self._check_document_access(doc, user_permissions, max_access_level):
                        filtered_docs.append(doc)
                    else:
                        permission_filtered_count += 1
                
                filtered_results[collection] = filtered_docs
            
            return {
                **state,
                "filtered_retrieval_results": filtered_results,
                "permission_filtered_count": permission_filtered_count
            }
            
        except Exception as e:
            logger.error(f"Document filtering failed: {e}")
            return {
                **state,
                "filtered_retrieval_results": state.get("raw_retrieval_results", {}),
                "permission_filtered_count": 0,
                "warnings": state.get("warnings", []) + [f"Document filtering error: {str(e)}"]
            }
    
    def _check_document_access(self, doc: Dict[str, Any], user_permissions: List[str], max_access_level) -> bool:
        """Check access to specific document"""
        doc_metadata = doc.get("metadata", {})
        
        # Check access level
        doc_access_level = doc_metadata.get("access_level", "public")
        if not self._access_level_permitted(doc_access_level, max_access_level):
            return False
        
        # Check required permissions
        required_perms = doc_metadata.get("required_permissions", [])
        if required_perms and not any(perm in user_permissions for perm in required_perms):
            return False
        
        return True
    
    def _access_level_permitted(self, doc_level: str, user_max_level) -> bool:
        """Check if user can access document level"""
        level_hierarchy = {
            "public": 1,
            "internal": 2, 
            "confidential": 3,
            "restricted": 4
        }
        
        user_level_value = level_hierarchy.get(
            user_max_level.value if hasattr(user_max_level, 'value') else str(user_max_level), 
            1
        )
        doc_level_value = level_hierarchy.get(doc_level, 1)
        
        return user_level_value >= doc_level_value
