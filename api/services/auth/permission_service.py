from typing import List, Dict, Any, Optional, Set
from datetime import datetime
import asyncio
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_

from models.database.user import User
from models.database.permission import Permission, UserPermission
from models.database.audit_log import AuditLog
from workflows.state.workflow_state import (
    UserContext, 
    AccessLevel, 
    AuditLogEntry,
    DocumentMetadata
)
from core.exceptions import PermissionDeniedError, InvalidAccessError


class PermissionService:
    """
    Core permission service cho hệ thống RAG
    Xử lý tất cả permission checking, access control và audit logging
    """
    
    def __init__(self, db_session: AsyncSession):
        self.db = db_session
        self._permission_cache: Dict[str, Dict] = {}
        self._cache_ttl = 300  # 5 minutes
    
    async def validate_user_access(
        self, 
        user_id: str, 
        resource_type: str, 
        resource_id: str,
        required_access_level: AccessLevel = AccessLevel.PUBLIC
    ) -> bool:
        """
        Validate user có quyền truy cập resource hay không
        """
        try:
            user_context = await self.get_user_context(user_id)
            
            # Check basic user validity
            if not user_context:
                await self._log_access_attempt(
                    user_id, resource_type, resource_id, False, 
                    reason="User not found"
                )
                return False
            
            # Check user access level
            if not self._check_access_level(user_context, required_access_level):
                await self._log_access_attempt(
                    user_id, resource_type, resource_id, False,
                    reason=f"Insufficient access level. Required: {required_access_level}"
                )
                return False
            
            # Check specific permissions
            has_permission = await self._check_resource_permission(
                user_context, resource_type, resource_id
            )
            
            await self._log_access_attempt(
                user_id, resource_type, resource_id, has_permission
            )
            
            return has_permission
            
        except Exception as e:
            await self._log_access_attempt(
                user_id, resource_type, resource_id, False,
                reason=f"Error during validation: {str(e)}"
            )
            return False
    
    async def get_user_context(self, user_id: str) -> Optional[UserContext]:
        """
        Lấy user context với full permission information
        """
        cache_key = f"user_context:{user_id}"
        
        # Check cache
        if cache_key in self._permission_cache:
            cached_data = self._permission_cache[cache_key]
            if (datetime.now() - cached_data['timestamp']).seconds < self._cache_ttl:
                return cached_data['data']
        
        # Query database
        query = select(User).where(User.id == user_id)
        result = await self.db.execute(query)
        user = result.scalar_one_or_none()
        
        if not user:
            return None
        
        # Get user permissions
        permissions = await self._get_user_permissions(user_id)
        access_levels = await self._get_user_access_levels(user_id)
        
        user_context = UserContext(
            user_id=user.id,
            username=user.username,
            email=user.email,
            department=user.department,
            role=user.role,
            permissions=permissions,
            access_levels=access_levels,
            tenant_id=user.tenant_id,
            last_login=user.last_login,
            session_expires=user.session_expires
        )
        
        # Cache result
        self._permission_cache[cache_key] = {
            'data': user_context,
            'timestamp': datetime.now()
        }
        
        return user_context
    
    async def get_accessible_collections(self, user_id: str) -> List[str]:
        """
        Lấy danh sách collections user có thể truy cập
        """
        user_context = await self.get_user_context(user_id)
        if not user_context:
            return []
        
        accessible_collections = []
        
        # Public collections - everyone can access
        accessible_collections.append("public_knowledge")
        
        # Department-specific collections
        dept_collection = f"{user_context['department'].lower()}_department"
        accessible_collections.append(dept_collection)
        
        # Cross-department collections based on permissions
        if "CROSS_DEPT_ACCESS" in user_context['permissions']:
            accessible_collections.append("cross_department_shared")
        
        # Manager/Executive access to multiple departments
        if user_context['role'] in ['MANAGER', 'DIRECTOR', 'CEO']:
            if "HR_ACCESS" in user_context['permissions']:
                accessible_collections.append("hr_department")
            if "IT_ACCESS" in user_context['permissions']:
                accessible_collections.append("it_department")
            if "FINANCE_ACCESS" in user_context['permissions']:
                accessible_collections.append("finance_department")
        
        return list(set(accessible_collections))
    
    async def filter_documents_by_permission(
        self, 
        user_id: str, 
        documents: List[DocumentMetadata]
    ) -> List[DocumentMetadata]:
        """
        Filter documents dựa trên user permissions
        """
        user_context = await self.get_user_context(user_id)
        if not user_context:
            return []
        
        filtered_docs = []
        
        for doc in documents:
            if await self._can_access_document(user_context, doc):
                filtered_docs.append(doc)
            else:
                await self._log_document_access_denied(user_id, doc)
        
        return filtered_docs
    
    async def get_user_tool_permissions(self, user_id: str) -> Dict[str, List[str]]:
        """
        Lấy danh sách tools user có thể sử dụng
        """
        user_context = await self.get_user_context(user_id)
        if not user_context:
            return {}
        
        tool_permissions = {}
        
        # Basic tools for all users
        tool_permissions["search_tools"] = ["basic_search", "semantic_search"]
        
        # Department-specific tools
        dept = user_context['department'].lower()
        if dept == "hr":
            tool_permissions["hr_tools"] = ["employee_search", "policy_lookup"]
        elif dept == "it":
            tool_permissions["it_tools"] = ["code_search", "documentation_lookup", "api_search"]
        elif dept == "finance":
            tool_permissions["finance_tools"] = ["financial_reports", "budget_analysis"]
        
        # Role-based tools
        if user_context['role'] in ['MANAGER', 'DIRECTOR']:
            tool_permissions["management_tools"] = ["team_analytics", "performance_reports"]
        
        if user_context['role'] == 'CEO':
            tool_permissions["executive_tools"] = ["company_analytics", "strategic_reports"]
        
        # Permission-based tools
        if "EXTERNAL_API_ACCESS" in user_context['permissions']:
            tool_permissions["external_tools"] = ["web_search", "external_integrations"]
        
        return tool_permissions
    
    async def check_tool_permission(
        self, 
        user_id: str, 
        tool_id: str, 
        tool_category: str
    ) -> bool:
        """
        Check user có permission sử dụng specific tool không
        """
        tool_permissions = await self.get_user_tool_permissions(user_id)
        
        for category, tools in tool_permissions.items():
            if tool_category == category and tool_id in tools:
                await self._log_tool_access(user_id, tool_id, True)
                return True
        
        await self._log_tool_access(user_id, tool_id, False)
        return False
    
    async def create_access_audit_entry(
        self,
        user_id: str,
        action: str,
        resource_type: str,
        resource_id: str,
        access_granted: bool,
        additional_data: Dict[str, Any] = None
    ) -> AuditLogEntry:
        """
        Tạo audit log entry cho mọi access attempt
        """
        audit_entry = AuditLogEntry(
            timestamp=datetime.now(),
            user_id=user_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            access_granted=access_granted,
            permission_checked=[],
            ip_address="",  # Will be filled by middleware
            user_agent="",  # Will be filled by middleware
            session_id="",  # Will be filled by middleware
            details=additional_data or {}
        )
        
        # Save to database
        await self._save_audit_log(audit_entry)
        
        return audit_entry
    
    # Private helper methods
    
    async def _get_user_permissions(self, user_id: str) -> List[str]:
        """Get list of permission strings for user"""
        query = select(Permission.permission_name).join(
            UserPermission, Permission.id == UserPermission.permission_id
        ).where(UserPermission.user_id == user_id)
        
        result = await self.db.execute(query)
        return [row[0] for row in result.fetchall()]
    
    async def _get_user_access_levels(self, user_id: str) -> List[AccessLevel]:
        """Get user access levels"""
        user_context = await self.get_user_context(user_id)
        if not user_context:
            return [AccessLevel.PUBLIC]
        
        access_levels = [AccessLevel.PUBLIC]
        
        if user_context['role'] in ['EMPLOYEE', 'STAFF']:
            access_levels.append(AccessLevel.INTERNAL)
        
        if user_context['role'] in ['MANAGER', 'SENIOR']:
            access_levels.extend([AccessLevel.INTERNAL, AccessLevel.CONFIDENTIAL])
        
        if user_context['role'] in ['DIRECTOR', 'CEO']:
            access_levels.extend([
                AccessLevel.INTERNAL, 
                AccessLevel.CONFIDENTIAL, 
                AccessLevel.RESTRICTED
            ])
        
        return access_levels
    
    def _check_access_level(
        self, 
        user_context: UserContext, 
        required_level: AccessLevel
    ) -> bool:
        """Check if user has required access level"""
        return required_level in user_context['access_levels']
    
    async def _check_resource_permission(
        self,
        user_context: UserContext,
        resource_type: str,
        resource_id: str
    ) -> bool:
        """Check specific resource permission"""
        # Department-based access
        if resource_type == "collection":
            if resource_id == "public_knowledge":
                return True
            
            if resource_id.startswith(user_context['department'].lower()):
                return True
            
            if resource_id == "cross_department_shared":
                return "CROSS_DEPT_ACCESS" in user_context['permissions']
        
        return False
    
    async def _can_access_document(
        self, 
        user_context: UserContext, 
        doc: DocumentMetadata
    ) -> bool:
        """Check if user can access specific document"""
        # Check access level
        if doc['access_level'] not in user_context['access_levels']:
            return False
        
        # Check department access
        if doc['department'] != user_context['department']:
            if doc['department'] != "PUBLIC":
                required_perm = f"{doc['department']}_ACCESS"
                if required_perm not in user_context['permissions']:
                    return False
        
        # Check specific permissions
        for req_perm in doc['required_permissions']:
            if req_perm not in user_context['permissions']:
                return False
        
        return True
    
    async def _log_access_attempt(
        self,
        user_id: str,
        resource_type: str,
        resource_id: str,
        access_granted: bool,
        reason: str = ""
    ):
        """Log access attempt to audit trail"""
        await self.create_access_audit_entry(
            user_id=user_id,
            action="ACCESS_ATTEMPT",
            resource_type=resource_type,
            resource_id=resource_id,
            access_granted=access_granted,
            additional_data={"reason": reason}
        )
    
    async def _log_document_access_denied(
        self, 
        user_id: str, 
        doc: DocumentMetadata
    ):
        """Log when document access is denied"""
        await self.create_access_audit_entry(
            user_id=user_id,
            action="DOCUMENT_ACCESS_DENIED",
            resource_type="document",
            resource_id=doc['document_id'],
            access_granted=False,
            additional_data={
                "document_title": doc['title'],
                "required_access_level": doc['access_level'].value,
                "document_department": doc['department']
            }
        )
    
    async def _log_tool_access(self, user_id: str, tool_id: str, access_granted: bool):
        """Log tool access attempt"""
        await self.create_access_audit_entry(
            user_id=user_id,
            action="TOOL_ACCESS",
            resource_type="tool",
            resource_id=tool_id,
            access_granted=access_granted
        )
    
    async def _save_audit_log(self, audit_entry: AuditLogEntry):
        """Save audit log to database"""
        audit_log = AuditLog(
            timestamp=audit_entry['timestamp'],
            user_id=audit_entry['user_id'],
            action=audit_entry['action'],
            resource_type=audit_entry['resource_type'],
            resource_id=audit_entry['resource_id'],
            access_granted=audit_entry['access_granted'],
            details=audit_entry['details']
        )
        
        self.db.add(audit_log)
        await self.db.commit()