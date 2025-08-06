"""
Permission Service
Manages permissions, tenant configurations, and user operations
"""
from typing import List, Dict, Any, Optional, Set
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, delete, update
from sqlalchemy.orm import joinedload, selectinload
from datetime import datetime
import uuid

from models.database.user import User
from models.database.permission import Permission, Group, UserPermission, GroupPermission, UserGroupMembership
from models.database.tenant import Tenant, Department
from models.database.tool import Tool, DepartmentToolConfig
from models.database.provider import Provider, DepartmentProviderConfig
from models.database.agent import Agent
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

logger = get_logger(__name__)
settings = get_settings()


class PermissionService:
    """
    Service for managing permissions and tenant configurations
    """
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    # ==================== TENANT OPERATIONS ====================
    
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
    
    async def soft_delete_tenant(self, tenant_id: str, deleted_by: str) -> bool:
        """
        Soft delete tenant (set is_active = False)
        """
        try:
            result = await self.db.execute(
                update(Tenant)
                .where(Tenant.id == tenant_id)
                .values(
                    is_active=False,
                    updated_at=datetime.utcnow(),
                    updated_by=deleted_by
                )
            )
            
            await self.db.commit()
            success = result.rowcount > 0
            
            if success:
                logger.info(f"Soft deleted tenant {tenant_id}")
            else:
                logger.warning(f"Tenant {tenant_id} not found for soft delete")
                
            return success
            
        except Exception as e:
            await self.db.rollback()
            logger.error(f"Failed to soft delete tenant: {e}")
            raise
    
    async def hard_delete_tenant(self, tenant_id: str) -> bool:
        """
        Permanently delete tenant and all related data
        """
        try:
            result = await self.db.execute(
                delete(Tenant).where(Tenant.id == tenant_id)
            )
            
            await self.db.commit()
            success = result.rowcount > 0
            
            if success:
                logger.info(f"Hard deleted tenant {tenant_id}")
            else:
                logger.warning(f"Tenant {tenant_id} not found for hard delete")
                
            return success
            
        except Exception as e:
            await self.db.rollback()
            logger.error(f"Failed to hard delete tenant: {e}")
            raise
    
    async def get_tenant_list(self, include_inactive: bool = False) -> List[Dict[str, Any]]:
        """
        Get list of all tenants
        """
        try:
            query = select(Tenant)
            if not include_inactive:
                query = query.where(Tenant.is_active == True)
                
            result = await self.db.execute(query.order_by(Tenant.created_at.desc()))
            tenants = result.scalars().all()
            
            tenant_list = []
            for tenant in tenants:
                tenant_list.append({
                    "tenant_id": str(tenant.id),
                    "tenant_name": tenant.tenant_name,
                    "is_active": tenant.is_active,
                    "created_at": tenant.created_at.isoformat() if tenant.created_at else None,
                    "created_by": tenant.created_by,
                    "config": tenant.config or {}
                })
            
            return tenant_list
            
        except Exception as e:
            logger.error(f"Failed to get tenant list: {e}")
            return []
    
    # ==================== DEPARTMENT OPERATIONS ====================
    
    async def create_department_with_agent(
        self,
        tenant_id: str,
        department_name: str,
        description: Optional[str] = None,
        created_by: str = None
    ) -> Dict[str, Any]:
        """
        Create department and automatically create corresponding agent
        """
        try:
            department = Department(
                id=str(uuid.uuid4()),
                tenant_id=tenant_id,
                department_name=department_name,
                description=description,
                is_active=True,
                created_at=datetime.utcnow(),
                created_by=created_by
            )
            self.db.add(department)
            
            agent = Agent(
                id=str(uuid.uuid4()),
                agent_name=f"{department_name}_Agent",
                description=f"Default agent for {department_name} department",
                department_id=str(department.id),
                is_system=True,
                is_enabled=True,
                created_at=datetime.utcnow(),
                created_by=created_by
            )
            self.db.add(agent)
            
            await self.db.commit()
            logger.info(f"Created department {department_name} with agent")
            
            return {
                "department_id": str(department.id),
                "department_name": department.department_name,
                "agent_id": str(agent.id),
                "agent_name": agent.agent_name,
                "status": "created"
            }
            
        except Exception as e:
            await self.db.rollback()
            logger.error(f"Failed to create department with agent: {e}")
            raise
    
    async def delete_department(self, department_id: str) -> bool:
        """
        Delete department and related agents
        """
        try:
            await self.db.execute(
                delete(Agent).where(Agent.department_id == department_id)
            )
            
            result = await self.db.execute(
                delete(Department).where(Department.id == department_id)
            )
            
            await self.db.commit()
            success = result.rowcount > 0
            
            if success:
                logger.info(f"Deleted department {department_id} and related agents")
            else:
                logger.warning(f"Department {department_id} not found")
                
            return success
            
        except Exception as e:
            await self.db.rollback()
            logger.error(f"Failed to delete department: {e}")
            raise
    
    async def get_departments_by_tenant(self, tenant_id: str) -> List[Dict[str, Any]]:
        """
        Get all departments for a tenant
        """
        try:
            result = await self.db.execute(
                select(Department)
                .where(Department.tenant_id == tenant_id)
                .where(Department.is_active == True)
                .order_by(Department.created_at)
            )
            departments = result.scalars().all()
            
            dept_list = []
            for dept in departments:
                dept_list.append({
                    "department_id": str(dept.id),
                    "department_name": dept.department_name,
                    "description": dept.description,
                    "is_active": dept.is_active,
                    "created_at": dept.created_at.isoformat() if dept.created_at else None
                })
            
            return dept_list
            
        except Exception as e:
            logger.error(f"Failed to get departments: {e}")
            return []
    
    # ==================== USER OPERATIONS ====================
    
    async def create_user_invitation(
        self,
        email: str,
        role: str,
        tenant_id: str,
        department_id: Optional[str] = None,
        invited_by: str = None
    ) -> Dict[str, Any]:
        """
        Create user invitation record
        """
        try:
            result = await self.db.execute(
                select(User).where(User.email == email)
            )
            existing_user = result.scalar_one_or_none()
            
            if existing_user:
                return {
                    "status": "user_exists",
                    "message": "User already exists in system"
                }
            
            user = User(
                id=str(uuid.uuid4()),
                email=email,
                username=email.split('@')[0], 
                role=role,
                tenant_id=tenant_id,
                department_id=department_id,
                is_active=False,  
                is_verified=False,
                created_at=datetime.utcnow(),
                created_by=invited_by
            )
            self.db.add(user)
            
            await self.db.commit()
            logger.info(f"Created invitation for {email} as {role}")
            
            return {
                "user_id": str(user.id),
                "email": email,
                "role": role,
                "status": "invitation_created"
            }
            
        except Exception as e:
            await self.db.rollback()
            logger.error(f"Failed to create user invitation: {e}")
            raise
    
    async def assign_user_to_group(
        self,
        user_id: str,
        group_id: str,
        assigned_by: Optional[str] = None
    ) -> bool:
        """
        Assign user to a group
        """
        try:
            result = await self.db.execute(
                select(UserGroupMembership)
                .where(UserGroupMembership.user_id == user_id)
                .where(UserGroupMembership.group_id == group_id)
            )
            existing = result.scalar_one_or_none()
            
            if existing:
                return True 
            
            membership = UserGroupMembership(
                id=str(uuid.uuid4()),
                user_id=user_id,
                group_id=group_id,
                assigned_by=assigned_by,
                created_at=datetime.utcnow()
            )
            self.db.add(membership)
            
            await self.db.commit()
            logger.info(f"Assigned user {user_id} to group {group_id}")
            return True
            
        except Exception as e:
            await self.db.rollback()
            logger.error(f"Failed to assign user to group: {e}")
            raise
    
    async def grant_user_permission(
        self,
        user_id: str,
        permission_code: str,
        granted_by: Optional[str] = None
    ) -> bool:
        """
        Grant direct permission to user
        """
        try:
            result = await self.db.execute(
                select(Permission).where(Permission.permission_code == permission_code)
            )
            permission = result.scalar_one_or_none()
            
            if not permission:
                logger.warning(f"Permission {permission_code} not found")
                return False
        
            result = await self.db.execute(
                select(UserPermission)
                .where(UserPermission.user_id == user_id)
                .where(UserPermission.permission_id == str(permission.id))
            )
            existing = result.scalar_one_or_none()
            
            if existing:
                return True  
            
            user_permission = UserPermission(
                id=str(uuid.uuid4()),
                user_id=user_id,
                permission_id=str(permission.id),
                granted_by=granted_by,
                created_at=datetime.utcnow()
            )
            self.db.add(user_permission)
            
            await self.db.commit()
            logger.info(f"Granted permission {permission_code} to user {user_id}")
            return True
            
        except Exception as e:
            await self.db.rollback()
            logger.error(f"Failed to grant user permission: {e}")
            raise
    
    # ==================== PERMISSION CHECKING ====================
    
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
                    selectinload(User.permissions).joinedload(UserPermission.permission),
                    selectinload(User.group_memberships).joinedload(UserGroupMembership.group)
                    .selectinload(Group.permissions).joinedload(GroupPermission.permission)
                )
                .where(User.id == user_id)
                .where(User.is_active == True)
            )
            
            user = result.scalar_one_or_none()
            if not user:
                return False
            
            for user_perm in user.permissions:
                if user_perm.permission.permission_code == permission_code:
                    return True
            
            for membership in user.group_memberships:
                group = membership.group
                for group_perm in group.permissions:
                    if group_perm.permission.permission_code == permission_code:
                        return True
            
            return False
            
        except Exception as e:
            logger.error(f"Failed to check user permission: {e}")
            return False
    
    async def get_user_permissions(self, user_id: str) -> List[str]:
        """
        Get all permissions for a user (direct + group permissions)
        """
        try:
            result = await self.db.execute(
                select(User)
                .options(
                    selectinload(User.permissions).joinedload(UserPermission.permission),
                    selectinload(User.group_memberships).joinedload(UserGroupMembership.group)
                    .selectinload(Group.permissions).joinedload(GroupPermission.permission)
                )
                .where(User.id == user_id)
                .where(User.is_active == True)
            )
            
            user = result.scalar_one_or_none()
            if not user:
                return []
            
            permissions = set()
            
            for user_perm in user.permissions:
                permissions.add(user_perm.permission.permission_code)
            
            for membership in user.group_memberships:
                group = membership.group
                for group_perm in group.permissions:
                    permissions.add(group_perm.permission.permission_code)
            
            return list(permissions)
            
        except Exception as e:
            logger.error(f"Failed to get user permissions: {e}")
            return []
    
    # ==================== PRIVATE HELPER METHODS ====================
    
    async def _create_default_groups(self, tenant_id: str) -> Dict[str, str]:
        """
        Create default groups for tenant (exclude MAINTAINER - it's system-wide)
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
        Setup default permissions for groups (exclude MAINTAINER permissions)
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
                    
                    dept_tool_config = DepartmentToolConfig(
                        id=str(uuid.uuid4()),
                        department_id=str(department.id),
                        tool_id=str(tool.id),
                        is_enabled=False,
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