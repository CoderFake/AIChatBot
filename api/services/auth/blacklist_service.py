"""
Permission Service
Manages permissions and tenant configurations
"""
from typing import List, Dict, Any, Optional, Set
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, delete
from sqlalchemy.orm import joinedload
from datetime import datetime
import uuid

from models.database.user import User
from models.database.permission import Permission, Group, UserPermission, GroupPermission, UserGroupMembership
from models.database.tenant import Tenant, Department
from models.database.tool import Tool, DepartmentToolConfig
from models.database.provider import Provider, DepartmentProviderConfig
from common.types import (
    AccessLevel,
    UserRole,
    RolePermissions,
    DefaultGroupNames,
    DefaultProviderConfig,
    DBDocumentPermissionLevel
)
from config.settings import get_settings
from utils.logging import get_logger
from core.exceptions import PermissionDeniedError, NotFoundError

logger = get_logger(__name__)
settings = get_settings()


class PermissionService:
    """
    Service for managing permissions and tenant configurations
    Uses correct database model names and relationships
    """
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def create_tenant_with_defaults(
        self,
        tenant_name: str,
        created_by: str,
        config: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Create new tenant with default permissions and configurations
        Sets up default groups, roles, and tool/provider access
        """
        try:
            tenant = Tenant(
                id=str(uuid.uuid4()),
                tenant_name=tenant_name,
                config=config or {},
                is_active=True,
                created_at=datetime.utcnow(),
                created_by=created_by
            )
            self.db.add(tenant)
            
            default_groups = await self._create_default_groups(tenant.id)
            
            await self._setup_default_permissions(tenant.id, default_groups)
            
            await self._setup_default_tools(tenant.id)
            
            await self._setup_default_provider(tenant.id)
            
            await self.db.commit()
            
            logger.info(f"Created tenant {tenant_name} with defaults")
            
            return {
                "tenant_id": tenant.id,
                "tenant_name": tenant.tenant_name,
                "groups": default_groups,
                "status": "created"
            }
            
        except Exception as e:
            await self.db.rollback()
            logger.error(f"Failed to create tenant: {e}")
            raise
    
    async def _create_default_groups(self, tenant_id: str) -> Dict[str, str]:
        """
        Create default groups for tenant
        Uses Group model from database
        """
        try:
            default_groups = {}
            
            groups_to_create = [
                ("ADMIN", DefaultGroupNames.ADMIN, "ROLE"), 
                ("DEPT_ADMIN", DefaultGroupNames.DEPT_ADMIN, "ROLE"),
                ("DEPT_MANAGER", DefaultGroupNames.DEPT_MANAGER, "ROLE"),
                ("USER", DefaultGroupNames.USER, "ROLE")
            ]
            
            for group_code, group_name, group_type in groups_to_create:
                group = Group(
                    id=str(uuid.uuid4()),
                    group_code=f"{tenant_id}_{group_code}",
                    group_name=group_name,
                    description=DefaultGroupNames.DESCRIPTIONS.get(group_name, f"Default {group_name} group"),
                    group_type=group_type,
                    is_system=True,
                    created_at=datetime.utcnow()
                )
                self.db.add(group)
                default_groups[group_code] = str(group.id)
            
            logger.info(f"Created {len(default_groups)} default groups for tenant {tenant_id}")
            return default_groups
            
        except Exception as e:
            logger.error(f"Failed to create default groups: {e}")
            raise
    
    async def _setup_default_permissions(self, tenant_id: str, groups: Dict[str, str]) -> None:
        """
        Setup default permissions for groups
        Uses Permission, GroupPermission models
        MAINTAINER permissions are system-wide, not tenant-specific
        """
        try:
            result = await self.db.execute(select(Permission))
            all_permissions = {p.permission_code: p for p in result.scalars().all()}
            
            role_permissions = {
                "ADMIN": RolePermissions.ADMIN_PERMISSIONS,
                "DEPT_ADMIN": RolePermissions.DEPT_ADMIN_PERMISSIONS,
                "DEPT_MANAGER": RolePermissions.DEPT_MANAGER_PERMISSIONS,
                "USER": RolePermissions.USER_PERMISSIONS
            }
            
            for role, permissions in role_permissions.items():
                if role in groups:
                    group_id = groups[role]
                    
                    for permission_code in permissions:
                        if hasattr(permission_code, 'value'):
                            permission_code = permission_code.value
                        
                        if permission_code in all_permissions:
                            group_permission = GroupPermission(
                                id=str(uuid.uuid4()),
                                group_id=group_id,
                                permission_id=str(all_permissions[permission_code].id),
                                granted_by=None,
                                created_at=datetime.utcnow()
                            )
                            self.db.add(group_permission)
            
            logger.info(f"Setup default permissions for tenant {tenant_id}")
            
        except Exception as e:
            logger.error(f"Failed to setup default permissions: {e}")
            raise
    
    async def _setup_default_tools(self, tenant_id: str) -> None:
        """
        Setup default tool configurations for tenant departments
        Uses Tool, DepartmentToolConfig models
        """
        try:
            result = await self.db.execute(
                select(Tool).where(Tool.is_enabled == True)
            )
            tools = result.scalars().all()
            
            dept_result = await self.db.execute(
                select(Department).where(Department.tenant_id == tenant_id)
            )
            departments = dept_result.scalars().all()
            
            for department in departments:
                for tool in tools:
                    is_enabled = tool.category in ["document_tools", "calculation_tools"]
                    
                    dept_tool_config = DepartmentToolConfig(
                        id=str(uuid.uuid4()),
                        department_id=str(department.id),
                        tool_id=str(tool.id),
                        is_enabled=is_enabled,
                        config_data={},
                        usage_limits={},
                        created_at=datetime.utcnow()
                    )
                    self.db.add(dept_tool_config)
            
            logger.info(f"Setup default tools for tenant {tenant_id}")
            
        except Exception as e:
            logger.error(f"Failed to setup default tools: {e}")
            raise
    
    async def _setup_default_provider(self, tenant_id: str) -> None:
        """
        Setup default provider configuration (Gemini)
        Uses Provider, DepartmentProviderConfig models
        """
        try:
            result = await self.db.execute(
                select(Provider).where(Provider.provider_name == "gemini")
            )
            provider = result.scalar_one_or_none()
            
            if not provider:
                logger.warning("Gemini provider not found, skipping default setup")
                return
            
            dept_result = await self.db.execute(
                select(Department).where(Department.tenant_id == tenant_id)
            )
            departments = dept_result.scalars().all()
            
            for department in departments:
                dept_provider_config = DepartmentProviderConfig(
                    id=str(uuid.uuid4()),
                    department_id=str(department.id),
                    provider_id=str(provider.id),
                    is_enabled=True,
                    model_name=DefaultProviderConfig.DEFAULT_MODEL,
                    config_data=DefaultProviderConfig.get_default_config(),
                    created_at=datetime.utcnow()
                )
                self.db.add(dept_provider_config)
            
            logger.info(f"Setup default provider for tenant {tenant_id}")
            
        except Exception as e:
            logger.error(f"Failed to setup default provider: {e}")
            raise
    
    async def check_user_permission(
        self,
        user_id: str,
        permission_code: str,
        resource_context: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Check if user has specific permission
        """
        try:
            result = await self.db.execute(
                select(User)
                .options(
                    joinedload(User.permissions).joinedload(UserPermission.permission),
                    joinedload(User.group_memberships).joinedload(UserGroupMembership.group)
                    .joinedload(Group.permissions).joinedload(GroupPermission.permission)
                )
                .where(User.id == user_id)
                .where(User.is_active == True)
            )
            
            user = result.scalar_one_or_none()
            if not user:
                return False
            
            user_permissions = {up.permission.permission_code for up in user.permissions if up.permission}
            if permission_code in user_permissions:
                return True
            
            for membership in user.group_memberships:
                if membership.group and membership.group.permissions:
                    group_permissions = {gp.permission.permission_code for gp in membership.group.permissions if gp.permission}
                    if permission_code in group_permissions:
                        return True
            
            return False
            
        except Exception as e:
            logger.error(f"Failed to check user permission: {e}")
            return False
    
    async def get_user_permissions(self, user_id: str) -> Set[str]:
        """
        Get all permissions for user
        """
        try:
            result = await self.db.execute(
                select(User)
                .options(
                    joinedload(User.permissions).joinedload(UserPermission.permission),
                    joinedload(User.group_memberships).joinedload(UserGroupMembership.group)
                    .joinedload(Group.permissions).joinedload(GroupPermission.permission)
                )
                .where(User.id == user_id)
                .where(User.is_active == True)
            )
            
            user = result.scalar_one_or_none()
            if not user:
                return set()
            
            permissions = set()
            
            for up in user.permissions:
                if up.permission:
                    permissions.add(up.permission.permission_code)
            
            for membership in user.group_memberships:
                if membership.group and membership.group.permissions:
                    for gp in membership.group.permissions:
                        if gp.permission:
                            permissions.add(gp.permission.permission_code)
            
            return permissions
            
        except Exception as e:
            logger.error(f"Failed to get user permissions: {e}")
            return set()
    
    async def assign_user_to_group(
        self, 
        user_id: str, 
        group_id: str, 
        added_by: Optional[str] = None,
        role_in_group: str = "MEMBER"
    ) -> bool:
        """
        Assign user to group
        """
        try:
            existing = await self.db.execute(
                select(UserGroupMembership)
                .where(
                    and_(
                        UserGroupMembership.user_id == user_id,
                        UserGroupMembership.group_id == group_id
                    )
                )
            )
            
            if existing.scalar_one_or_none():
                logger.warning(f"User {user_id} already in group {group_id}")
                return False
            
            membership = UserGroupMembership(
                id=str(uuid.uuid4()),
                user_id=user_id,
                group_id=group_id,
                added_by=added_by,
                role_in_group=role_in_group,
                created_at=datetime.utcnow()
            )
            
            self.db.add(membership)
            await self.db.commit()
            
            logger.info(f"User {user_id} assigned to group {group_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to assign user to group: {e}")
            await self.db.rollback()
            return False
    
    async def remove_user_from_group(self, user_id: str, group_id: str) -> bool:
        """
        Remove user from group
        """
        try:
            result = await self.db.execute(
                delete(UserGroupMembership)
                .where(
                    and_(
                        UserGroupMembership.user_id == user_id,
                        UserGroupMembership.group_id == group_id
                    )
                )
            )
            
            if result.rowcount > 0:
                await self.db.commit()
                logger.info(f"User {user_id} removed from group {group_id}")
                return True
            else:
                logger.warning(f"No membership found for user {user_id} in group {group_id}")
                return False
            
        except Exception as e:
            logger.error(f"Failed to remove user from group: {e}")
            await self.db.rollback()
            return False


class RAGPermissionService:
    """
    RAG-specific permission service for document access
    """
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def get_user_document_access_levels(
        self, 
        user_id: str, 
        department: str
    ) -> List[DBDocumentPermissionLevel]:
        """
        Get document access levels for user in department
        """
        try:
            permission_service = PermissionService(self.db)
            user_permissions = await permission_service.get_user_permissions(user_id)
            
            access_levels = []
            
            if any(perm in user_permissions for perm in [
                "document.public.read", "chat.public"
            ]):
                access_levels.append(DBDocumentPermissionLevel.PUBLIC)
            
            if any(perm in user_permissions for perm in [
                "document.private.read", "chat.private"
            ]):
                access_levels.append(DBDocumentPermissionLevel.PRIVATE)
            
            return access_levels if access_levels else [DBDocumentPermissionLevel.PUBLIC]
            
        except Exception as e:
            logger.error(f"Failed to get document access levels: {e}")
            return [DBDocumentPermissionLevel.PUBLIC]
    
    async def check_document_access(
        self,
        user_id: str,
        document_access_level: str,
        document_department: str,
        user_department: str
    ) -> bool:
        """
        Check if user can access document based on access level and department
        """
        try:
            if document_access_level == AccessLevel.PUBLIC.value:
                return True
            
            if document_access_level == AccessLevel.PRIVATE.value:
                return document_department == user_department
            
            permission_service = PermissionService(self.db)
            user_permissions = await permission_service.get_user_permissions(user_id)
            
            required_permissions = {
                AccessLevel.PRIVATE.value: ["document.private.read", "chat.private"]
            }
            
            if document_access_level in required_permissions:
                return any(perm in user_permissions for perm in required_permissions[document_access_level])
            
            return False
            
        except Exception as e:
            logger.error(f"Failed to check document access: {e}")
            return False