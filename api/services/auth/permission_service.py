from typing import List, Dict, Any, Optional, Set
from utils.datetime_utils import CustomDateTime as datetime
import asyncio
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_
from sqlalchemy.orm import joinedload

from models.database.user import User
from models.database.permission import Permission, UserPermission, Group, GroupPermission, UserGroupMembership, ToolPermission
from models.database.tool import Tool
from models.database.document import Document
from models.database.audit_log import AuditLog
from common.types import UserRole, Department
from config.settings import get_settings
from utils.logging import get_logger
from core.exceptions import PermissionDeniedError, NotFoundError

logger = get_logger(__name__)
settings = get_settings()

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
        action: str = "read",
        additional_context: Dict[str, Any] = None
    ) -> bool:
        """
        Validate user có quyền truy cập resource hay không
        
        Args:
            user_id: ID của user
            resource_type: Loại resource (document, tool, collection, etc.)
            resource_id: ID của resource
            action: Action cần check (read, write, delete, execute)
            additional_context: Context bổ sung
            
        Returns:
            bool: True nếu có quyền, False nếu không
        """
        try:
            user_permissions = await self.get_user_all_permissions(user_id)
            
            if not user_permissions:
                await self._log_access_attempt(
                    user_id, resource_type, resource_id, False, 
                    reason="User has no permissions"
                )
                return False
            
            # Check specific resource permission
            has_permission = await self._check_resource_permission(
                user_id, user_permissions, resource_type, resource_id, action, additional_context
            )
            
            await self._log_access_attempt(
                user_id, resource_type, resource_id, has_permission
            )
            
            return has_permission
            
        except Exception as e:
            logger.error(f"Permission validation error: {e}")
            await self._log_access_attempt(
                user_id, resource_type, resource_id, False,
                reason=f"Error during validation: {str(e)}"
            )
            return False
    
    async def get_user_all_permissions(self, user_id: str) -> Dict[str, Any]:
        """
        Lấy tất cả permissions của user (direct + từ groups)
        
        Returns:
            Dict chứa permissions, groups, department, role
        """
        cache_key = f"user_permissions:{user_id}"
        
        if cache_key in self._permission_cache:
            cached_data = self._permission_cache[cache_key]
            if (datetime.now() - cached_data['timestamp']).seconds < self._cache_ttl:
                return cached_data['data']
        
        try:
            query = select(User).options(
                joinedload(User.permissions).joinedload(UserPermission.permission),
                joinedload(User.group_memberships).joinedload(UserGroupMembership.group)
            ).where(User.id == user_id, User.is_active == True)
            
            result = await self.db.execute(query)
            user = result.scalar_one_or_none()
            
            if not user:
                return {}
            
            direct_permissions = set()
            for user_perm in user.permissions:
                if not user_perm.expires_at or user_perm.expires_at > datetime.now():
                    direct_permissions.add(user_perm.permission.permission_name)
            
            group_permissions = set()
            user_groups = []
            for membership in user.group_memberships:
                if not membership.expires_at or membership.expires_at > datetime.now():
                    user_groups.append(membership.group.group_name)
                    
                    group_perms_query = select(GroupPermission).options(
                        joinedload(GroupPermission.permission)
                    ).where(GroupPermission.group_id == membership.group.id)
                    
                    group_perms_result = await self.db.execute(group_perms_query)
                    for group_perm in group_perms_result.scalars():
                        group_permissions.add(group_perm.permission.permission_name)
            
            all_permissions = direct_permissions | group_permissions
            
            user_context = {
                "user_id": user.id,
                "username": user.username,
                "email": user.email,
                "department": user.department,
                "role": user.role,
                "permissions": list(all_permissions),
                "direct_permissions": list(direct_permissions),
                "group_permissions": list(group_permissions),
                "groups": user_groups,
                "is_active": user.is_active,
                "is_staff": user.is_staff,
                "is_superuser": user.is_superuser,
                "last_login": user.last_login
            }
            
            # Cache result
            self._permission_cache[cache_key] = {
                'data': user_context,
                'timestamp': datetime.now()
            }
            
            return user_context
            
        except Exception as e:
            logger.error(f"Failed to get user permissions: {e}")
            return {}
    
    async def get_accessible_collections(self, user_id: str) -> List[str]:
        """
        Lấy danh sách collections user có thể truy cập
        
        Returns:
            List of collection names
        """
        user_context = await self.get_user_all_permissions(user_id)
        if not user_context:
            return []
        
        accessible_collections = []
        permissions = user_context.get('permissions', [])
        department = user_context.get('department', '').lower()
        role = user_context.get('role', '')
        
        # Public collections - everyone can access
        accessible_collections.append("general_documents")
        
        # Department-specific collections
        if "hr_access" in permissions or department == Department.HR.value:
            accessible_collections.append("hr_documents")
            accessible_collections.append("hr_policies")
            
        if "finance_access" in permissions or department == Department.FINANCE.value:
            accessible_collections.append("finance_documents")
            accessible_collections.append("finance_reports")
            
        if "it_access" in permissions or department == Department.IT.value:
            accessible_collections.append("it_documents")
            accessible_collections.append("it_procedures")
        
        # Cross-department access
        if "cross_department_access" in permissions:
            accessible_collections.extend([
                "hr_documents", "hr_policies",
                "finance_documents", "finance_reports", 
                "it_documents", "it_procedures"
            ])
        
        if role in [UserRole.MANAGER.value, UserRole.DIRECTOR.value, UserRole.CEO.value, UserRole.ADMIN.value]:
            accessible_collections.extend([
                "hr_documents", "finance_documents", "it_documents"
            ])
        
        return list(set(accessible_collections))
    
    async def filter_documents_by_permission(
        self, 
        user_id: str, 
        documents: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Filter documents dựa trên user permissions
        
        Args:
            user_id: ID của user
            documents: List documents cần filter
            
        Returns:
            List documents user được phép truy cập
        """
        user_context = await self.get_user_all_permissions(user_id)
        if not user_context:
            return []
        
        filtered_docs = []
        
        for doc in documents:
            if await self._can_access_document(user_context, doc):
                filtered_docs.append(doc)
            else:
                await self._log_document_access_denied(user_id, doc)
        
        return filtered_docs
    
    async def get_user_tool_permissions(self, user_id: str) -> Dict[str, List[Dict[str, Any]]]:
        """
        Lấy danh sách tools user có thể sử dụng - database-driven approach
        
        Returns:
            Dict mapping tool categories to tool details lists
        """
        user_context = await self.get_user_all_permissions(user_id)
        if not user_context:
            return {}
        
        user_permissions = user_context.get('permissions', [])
        user_department = user_context.get('department', '')
        
        # Query tools với permissions từ database
        tools_query = select(Tool).options(
            joinedload(Tool.tool_permissions).joinedload(ToolPermission.permission)
        ).where(
            Tool.is_enabled == True
        )
        
        result = await self.db.execute(tools_query)
        available_tools = result.scalars().all()
        
        # Group tools by category
        user_tools = {}
        
        for tool in available_tools:
            # Check department restriction
            if not tool.is_available_for_department(user_department):
                continue
            
            # Check permission requirements
            has_access = False
            required_permissions = []
            
            for tool_perm in tool.tool_permissions:
                if tool_perm.is_enabled:
                    required_permissions.append(tool_perm.permission.permission_name)
                    if tool_perm.permission.permission_name in user_permissions:
                        has_access = True
                        break
            
            # Nếu tool không có permission requirements, default allow
            if not required_permissions:
                has_access = True
            
            if has_access:
                category = tool.category
                
                if category not in user_tools:
                    user_tools[category] = []
                
                # Tạo tool info với metadata từ database
                tool_info = {
                    "id": str(tool.id),
                    "name": tool.name,
                    "display_name": tool.display_name,
                    "description": tool.description,
                    "version": tool.version,
                    "config": tool.tool_config or {},
                    "usage_limits": tool.usage_limits or {},
                    "documentation_url": tool.documentation_url,
                    "required_permissions": required_permissions
                }
                
                user_tools[category].append(tool_info)
        
        return user_tools
    
    async def check_tool_permission(
        self, 
        user_id: str, 
        tool_name: str
    ) -> bool:
        """
        Check user có permission sử dụng specific tool không - database-driven approach
        
        Args:
            user_id: ID của user
            tool_name: Tên tool cần check
            
        Returns:
            bool: True nếu có quyền sử dụng
        """
        user_context = await self.get_user_all_permissions(user_id)
        if not user_context:
            return False
        
        user_permissions = user_context.get('permissions', [])
        user_department = user_context.get('department', '')
        
        # Get tool từ database
        tool_query = select(Tool).options(
            joinedload(Tool.tool_permissions).joinedload(ToolPermission.permission)
        ).where(
            Tool.name == tool_name,
            Tool.is_enabled == True
        )
        
        result = await self.db.execute(tool_query)
        tool = result.scalar_one_or_none()
        
        if not tool:
            await self._log_tool_access(user_id, tool_name, False, "Tool not found or disabled")
            return False
        
        # Check department restriction
        if not tool.is_available_for_department(user_department):
            await self._log_tool_access(user_id, tool_name, False, f"Tool not available for department: {user_department}")
            return False
        
        # Check permission requirements
        required_permissions = []
        has_permission = False
        
        for tool_perm in tool.tool_permissions:
            if tool_perm.is_enabled:
                required_permissions.append(tool_perm.permission.permission_name)
                if tool_perm.permission.permission_name in user_permissions:
                    has_permission = True
                    break
        
        # Nếu tool không có permission requirements, default allow
        if not required_permissions:
            has_permission = True
        
        await self._log_tool_access(
            user_id, 
            tool_name, 
            has_permission,
            f"Required: {required_permissions}, User has: {user_permissions}" if not has_permission else ""
        )
        
        return has_permission
    
    async def check_document_access(
        self,
        user_id: str,
        document_id: str,
        action: str = "read"
    ) -> bool:
        """
        Check user có thể access document cụ thể không
        
        Args:
            user_id: ID của user
            document_id: ID của document
            action: Action cần thực hiện (read, write, delete)
            
        Returns:
            bool: True nếu có quyền
        """
        user_context = await self.get_user_all_permissions(user_id)
        if not user_context:
            return False
        
        # Get document
        doc_query = select(Document).where(Document.id == document_id)
        result = await self.db.execute(doc_query)
        document = result.scalar_one_or_none()
        
        if not document:
            return False
        
        # Convert document to dict format
        doc_dict = {
            "id": str(document.id),
            "title": document.title,
            "department": document.department,
            "access_level": document.access_level,
            "required_permissions": document.required_permissions or [],
            "uploaded_by": str(document.uploaded_by)
        }
        
        return await self._can_access_document(user_context, doc_dict, action)
    
    async def add_user_to_group(self, user_id: str, group_name: str, added_by: str = None) -> bool:
        """
        Thêm user vào group
        
        Args:
            user_id: ID của user
            group_name: Tên group
            added_by: User thực hiện thêm
            
        Returns:
            bool: True nếu thành công
        """
        try:
            # Get group
            group_query = select(Group).where(Group.group_name == group_name)
            result = await self.db.execute(group_query)
            group = result.scalar_one_or_none()
            
            if not group:
                raise NotFoundError(f"Group {group_name} not found")
            
            # Check if already member
            existing_query = select(UserGroupMembership).where(
                UserGroupMembership.user_id == user_id,
                UserGroupMembership.group_id == str(group.id)
            )
            existing = await self.db.execute(existing_query)
            
            if existing.scalar_one_or_none():
                return True  # Already member
            
            # Add membership
            membership = UserGroupMembership(
                user_id=user_id,
                group_id=str(group.id),
                added_by=added_by,
                role_in_group="MEMBER"
            )
            
            self.db.add(membership)
            await self.db.commit()
            
            # Clear cache
            self._clear_user_cache(user_id)
            
            logger.info(f"Added user {user_id} to group {group_name}")
            return True
            
        except Exception as e:
            await self.db.rollback()
            logger.error(f"Failed to add user to group: {e}")
            return False
    
    async def remove_user_from_group(self, user_id: str, group_name: str) -> bool:
        """
        Xóa user khỏi group
        """
        try:
            # Get group
            group_query = select(Group).where(Group.group_name == group_name)
            result = await self.db.execute(group_query)
            group = result.scalar_one_or_none()
            
            if not group:
                return False
            
            # Remove membership
            membership_query = select(UserGroupMembership).where(
                UserGroupMembership.user_id == user_id,
                UserGroupMembership.group_id == str(group.id)
            )
            result = await self.db.execute(membership_query)
            membership = result.scalar_one_or_none()
            
            if membership:
                await self.db.delete(membership)
                await self.db.commit()
                
                # Clear cache
                self._clear_user_cache(user_id)
                
                logger.info(f"Removed user {user_id} from group {group_name}")
            
            return True
            
        except Exception as e:
            await self.db.rollback()
            logger.error(f"Failed to remove user from group: {e}")
            return False
    
    # Private helper methods
    
    async def _check_resource_permission(
        self,
        user_id: str,
        user_permissions: Dict[str, Any],
        resource_type: str,
        resource_id: str,
        action: str,
        additional_context: Dict[str, Any] = None
    ) -> bool:
        """Check specific resource permission"""
        
        permissions = user_permissions.get('permissions', [])
        department = user_permissions.get('department', '')
        role = user_permissions.get('role', '')
        
        if resource_type == "document":
            return await self.check_document_access(user_id, resource_id, action)
            
        elif resource_type == "tool":
            return await self.check_tool_permission(user_id, resource_id)
            
        elif resource_type == "collection":
            accessible_collections = await self.get_accessible_collections(user_id)
            return resource_id in accessible_collections
            
        elif resource_type == "admin":
            return any(perm.startswith("admin_") for perm in permissions)
        
        return False
    
    async def _can_access_document(
        self, 
        user_context: Dict[str, Any], 
        doc: Dict[str, Any],
        action: str = "read"
    ) -> bool:
        """Check if user can access specific document"""
        
        permissions = user_context.get('permissions', [])
        department = user_context.get('department', '')
        role = user_context.get('role', '')
        user_id = user_context.get('user_id', '')
        
        # Check if user is owner
        if doc.get('uploaded_by') == user_id:
            return True
        
        # Check access level permissions
        access_level = doc.get('access_level', 'public')
        
        if access_level == "public":
            return "document_read_public" in permissions
        elif access_level == "private":
            # Private docs only accessible by same department
            if doc.get('department', '').upper() != department.upper():
                return False
            return "document_read_internal" in permissions
        elif access_level == "internal":
            return "document_read_internal" in permissions
        elif access_level == "confidential":
            return "document_read_confidential" in permissions
        elif access_level == "restricted":
            return "document_read_restricted" in permissions
        
        # Check specific required permissions
        required_perms = doc.get('required_permissions', [])
        if required_perms:
            return any(perm in permissions for perm in required_perms)
        
        return False
    
    async def _log_access_attempt(
        self,
        user_id: str,
        resource_type: str,
        resource_id: str,
        access_granted: bool,
        reason: str = ""
    ):
        """Log access attempt to audit trail"""
        try:
            audit_log = AuditLog(
                user_id=user_id,
                action="ACCESS_ATTEMPT",
                resource_type=resource_type,
                resource_id=resource_id,
                action_result="SUCCESS" if access_granted else "DENIED",
                additional_data={"reason": reason} if reason else None,
                category="SECURITY_EVENT" if not access_granted else "USER_ACTION",
                severity="WARNING" if not access_granted else "INFO"
            )
            
            self.db.add(audit_log)
            await self.db.commit()
            
        except Exception as e:
            logger.error(f"Failed to log access attempt: {e}")
    
    async def _log_document_access_denied(self, user_id: str, doc: Dict[str, Any]):
        """Log when document access is denied"""
        await self._log_access_attempt(
            user_id=user_id,
            resource_type="document",
            resource_id=doc.get('id', 'unknown'),
            access_granted=False,
            reason=f"Insufficient permissions for document: {doc.get('title', 'Unknown')}"
        )
    
    async def _log_tool_access(self, user_id: str, tool_name: str, access_granted: bool, reason: str = ""):
        """Log tool access attempt"""
        await self._log_access_attempt(
            user_id=user_id,
            resource_type="tool",
            resource_id=tool_name,
            access_granted=access_granted,
            reason=reason
        )
    
    def _clear_user_cache(self, user_id: str):
        """Clear user permission cache"""
        cache_key = f"user_permissions:{user_id}"
        if cache_key in self._permission_cache:
            del self._permission_cache[cache_key]
    
    def clear_all_cache(self):
        """Clear all permission cache"""
        self._permission_cache.clear()
        logger.info("Permission cache cleared")