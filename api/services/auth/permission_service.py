"""
Permission Service
Core permission management: create default groups and validate user permissions
Does NOT handle CRUD operations for tenant/tools - those belong to respective services
"""
from typing import List, Dict, Any, Optional, Set
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, delete, update
from sqlalchemy.orm import joinedload, selectinload
from datetime import datetime
import uuid

from models.database.user import User
from models.database.permission import (
    Permission, 
    Group, 
    UserPermission, 
    GroupPermission, 
    UserGroupMembership
)
from common.types import (
    RolePermissions,
    DefaultGroupNames
)
from config.settings import get_settings
from utils.logging import get_logger

logger = get_logger(__name__)
settings = get_settings()


class PermissionService:
    """
    Core permission management service with two main responsibilities:
    1. Create default groups for new tenants (called by TenantService)
    2. Validate user permissions for API access (called by Middleware)
    """
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    # ==================== DEFAULT GROUPS CREATION ====================
    
    async def create_default_groups_for_tenant(
        self,
        tenant_id: str,
        created_by: Optional[str] = None
    ) -> Dict[str, str]:
        """
        Create default permission groups for a new tenant
        Called by TenantService when creating a new tenant
        Returns: Dict mapping role names to group IDs
        """
        try:
            default_groups = await self._create_default_groups(tenant_id)
            await self._setup_default_permissions(tenant_id, default_groups)
            
            logger.info(f"Created default groups for tenant {tenant_id}")
            return default_groups
            
        except Exception as e:
            logger.error(f"Failed to create default groups for tenant {tenant_id}: {e}")
            raise

    
    # ==================== PERMISSION CRUD OPERATIONS ====================
    
    async def create_permission(
        self,
        permission_code: str,
        permission_name: str,
        resource_type: str,
        action: str,
        description: Optional[str] = None,
        is_system: bool = False,
        created_by: Optional[str] = None
    ) -> Permission:
        """Create a new permission"""
        try:
            permission = Permission(
                id=str(uuid.uuid4()),
                permission_code=permission_code,
                permission_name=permission_name,
                description=description,
                resource_type=resource_type,
                action=action,
                is_system=is_system,
                created_by=created_by,
                created_at=datetime.utcnow()
            )
            
            self.db.add(permission)
            await self.db.commit()
            await self.db.refresh(permission)
            
            logger.info(f"Created permission: {permission_code}")
            return permission
            
        except Exception as e:
            logger.error(f"Failed to create permission {permission_code}: {e}")
            await self.db.rollback()
            raise
    
    async def get_permission_by_id(self, permission_id: str) -> Optional[Permission]:
        """Get permission by ID"""
        try:
            result = await self.db.execute(
                select(Permission)
                .where(Permission.id == permission_id)
                .where(Permission.is_deleted == False)
            )
            return result.scalar_one_or_none()
        except Exception as e:
            logger.error(f"Failed to get permission {permission_id}: {e}")
            return None
    
    async def get_permission_by_code(self, permission_code: str) -> Optional[Permission]:
        """Get permission by code"""
        try:
            result = await self.db.execute(
                select(Permission)
                .where(Permission.permission_code == permission_code)
                .where(Permission.is_deleted == False)
            )
            return result.scalar_one_or_none()
        except Exception as e:
            logger.error(f"Failed to get permission by code {permission_code}: {e}")
            return None
    
    async def list_permissions(
        self,
        resource_type: Optional[str] = None,
        action: Optional[str] = None,
        is_system: Optional[bool] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[Permission]:
        """List permissions with optional filters"""
        try:
            query = select(Permission).where(Permission.is_deleted == False)
            
            if resource_type:
                query = query.where(Permission.resource_type == resource_type)
            if action:
                query = query.where(Permission.action == action)
            if is_system is not None:
                query = query.where(Permission.is_system == is_system)
            
            query = query.offset(offset).limit(limit)
            
            result = await self.db.execute(query)
            return result.scalars().all()
            
        except Exception as e:
            logger.error(f"Failed to list permissions: {e}")
            return []
    
    async def update_permission(
        self,
        permission_id: str,
        permission_name: Optional[str] = None,
        description: Optional[str] = None,
        updated_by: Optional[str] = None
    ) -> Optional[Permission]:
        """Update permission (code, resource_type, action are immutable)"""
        try:
            permission = await self.get_permission_by_id(permission_id)
            if not permission:
                return None
            
            if permission_name:
                permission.permission_name = permission_name
            if description is not None:
                permission.description = description
            if updated_by:
                permission.updated_by = updated_by
            
            permission.updated_at = datetime.utcnow()
            
            await self.db.commit()
            await self.db.refresh(permission)
            
            logger.info(f"Updated permission: {permission.permission_code}")
            return permission
            
        except Exception as e:
            logger.error(f"Failed to update permission {permission_id}: {e}")
            await self.db.rollback()
            raise
    
    async def delete_permission(self, permission_id: str, deleted_by: Optional[str] = None) -> bool:
        """Soft delete permission (only if not system permission)"""
        try:
            permission = await self.get_permission_by_id(permission_id)
            if not permission:
                return False
            
            if permission.is_system:
                logger.warning(f"Cannot delete system permission: {permission.permission_code}")
                return False
            
            permission.soft_delete()
            if deleted_by:
                permission.updated_by = deleted_by
            
            await self.db.commit()
            
            logger.info(f"Deleted permission: {permission.permission_code}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to delete permission {permission_id}: {e}")
            await self.db.rollback()
            raise

    # ==================== GROUP CRUD OPERATIONS ====================
    
    async def create_group(
        self,
        group_code: str,
        group_name: str,
        group_type: str,
        description: Optional[str] = None,
        department_id: Optional[str] = None,
        is_system: bool = False,
        settings: Optional[Dict[str, Any]] = None,
        created_by: Optional[str] = None
    ) -> Group:
        """Create a new group"""
        try:
            group = Group(
                id=str(uuid.uuid4()),
                group_code=group_code,
                group_name=group_name,
                description=description,
                group_type=group_type,
                department_id=department_id,
                is_system=is_system,
                settings=settings,
                created_by=created_by,
                created_at=datetime.utcnow()
            )
            
            self.db.add(group)
            await self.db.commit()
            await self.db.refresh(group)
            
            logger.info(f"Created group: {group_code}")
            return group
            
        except Exception as e:
            logger.error(f"Failed to create group {group_code}: {e}")
            await self.db.rollback()
            raise
    
    async def get_group_by_id(self, group_id: str) -> Optional[Group]:
        """Get group by ID"""
        try:
            result = await self.db.execute(
                select(Group)
                .options(
                    selectinload(Group.permissions).joinedload(GroupPermission.permission),
                    selectinload(Group.members).joinedload(UserGroupMembership.user)
                )
                .where(Group.id == group_id)
                .where(Group.is_deleted == False)
            )
            return result.scalar_one_or_none()
        except Exception as e:
            logger.error(f"Failed to get group {group_id}: {e}")
            return None
    
    async def get_group_by_code(self, group_code: str) -> Optional[Group]:
        """Get group by code"""
        try:
            result = await self.db.execute(
                select(Group)
                .where(Group.group_code == group_code)
                .where(Group.is_deleted == False)
            )
            return result.scalar_one_or_none()
        except Exception as e:
            logger.error(f"Failed to get group by code {group_code}: {e}")
            return None
    
    async def list_groups(
        self,
        group_type: Optional[str] = None,
        department_id: Optional[str] = None,
        is_system: Optional[bool] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[Group]:
        """List groups with optional filters"""
        try:
            query = select(Group).where(Group.is_deleted == False)
            
            if group_type:
                query = query.where(Group.group_type == group_type)
            if department_id:
                query = query.where(Group.department_id == department_id)
            if is_system is not None:
                query = query.where(Group.is_system == is_system)
            
            query = query.offset(offset).limit(limit)
            
            result = await self.db.execute(query)
            return result.scalars().all()
            
        except Exception as e:
            logger.error(f"Failed to list groups: {e}")
            return []
    
    async def update_group(
        self,
        group_id: str,
        group_name: Optional[str] = None,
        description: Optional[str] = None,
        settings: Optional[Dict[str, Any]] = None,
        updated_by: Optional[str] = None
    ) -> Optional[Group]:
        """Update group"""
        try:
            group = await self.get_group_by_id(group_id)
            if not group:
                return None
            
            if group_name:
                group.group_name = group_name
            if description is not None:
                group.description = description
            if settings is not None:
                group.settings = settings
            if updated_by:
                group.updated_by = updated_by
            
            group.updated_at = datetime.utcnow()
            
            await self.db.commit()
            await self.db.refresh(group)
            
            logger.info(f"Updated group: {group.group_code}")
            return group
            
        except Exception as e:
            logger.error(f"Failed to update group {group_id}: {e}")
            await self.db.rollback()
            raise
    
    async def delete_group(self, group_id: str, deleted_by: Optional[str] = None) -> bool:
        """Soft delete group (only if not system group)"""
        try:
            group = await self.get_group_by_id(group_id)
            if not group:
                return False
            
            if group.is_system:
                logger.warning(f"Cannot delete system group: {group.group_code}")
                return False
            
            group.soft_delete()
            if deleted_by:
                group.updated_by = deleted_by
            
            await self.db.commit()
            
            logger.info(f"Deleted group: {group.group_code}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to delete group {group_id}: {e}")
            await self.db.rollback()
            raise

    # ==================== USER PERMISSION CRUD OPERATIONS ====================
    
    async def assign_permission_to_user(
        self,
        user_id: str,
        permission_id: str,
        granted_by: Optional[str] = None,
        expires_at: Optional[datetime] = None,
        conditions: Optional[Dict[str, Any]] = None
    ) -> UserPermission:
        """Assign permission directly to user"""
        try:
            # Check if permission already exists
            existing = await self.db.execute(
                select(UserPermission)
                .where(UserPermission.user_id == user_id)
                .where(UserPermission.permission_id == permission_id)
                .where(UserPermission.is_deleted == False)
            )
            
            if existing.scalar_one_or_none():
                raise ValueError("Permission already assigned to user")
            
            user_permission = UserPermission(
                id=str(uuid.uuid4()),
                user_id=user_id,
                permission_id=permission_id,
                granted_by=granted_by,
                expires_at=expires_at,
                conditions=conditions,
                created_by=granted_by,
                created_at=datetime.utcnow()
            )
            
            self.db.add(user_permission)
            await self.db.commit()
            await self.db.refresh(user_permission)
            
            logger.info(f"Assigned permission {permission_id} to user {user_id}")
            return user_permission
            
        except Exception as e:
            logger.error(f"Failed to assign permission to user: {e}")
            await self.db.rollback()
            raise
    
    async def revoke_permission_from_user(
        self,
        user_id: str,
        permission_id: str,
        revoked_by: Optional[str] = None
    ) -> bool:
        """Revoke permission from user"""
        try:
            result = await self.db.execute(
                select(UserPermission)
                .where(UserPermission.user_id == user_id)
                .where(UserPermission.permission_id == permission_id)
                .where(UserPermission.is_deleted == False)
            )
            
            user_permission = result.scalar_one_or_none()
            if not user_permission:
                return False
            
            user_permission.soft_delete()
            if revoked_by:
                user_permission.updated_by = revoked_by
            
            await self.db.commit()
            
            logger.info(f"Revoked permission {permission_id} from user {user_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to revoke permission from user: {e}")
            await self.db.rollback()
            raise
    
    async def get_user_direct_permissions(self, user_id: str) -> List[UserPermission]:
        """Get all direct permissions for a user"""
        try:
            result = await self.db.execute(
                select(UserPermission)
                .options(joinedload(UserPermission.permission))
                .where(UserPermission.user_id == user_id)
                .where(UserPermission.is_deleted == False)
            )
            return result.scalars().all()
            
        except Exception as e:
            logger.error(f"Failed to get user permissions: {e}")
            return []
    
    # ==================== GROUP PERMISSION CRUD OPERATIONS ====================
    
    async def assign_permission_to_group(
        self,
        group_id: str,
        permission_id: str,
        granted_by: Optional[str] = None,
        conditions: Optional[Dict[str, Any]] = None
    ) -> GroupPermission:
        """Assign permission to group"""
        try:
            # Check if permission already exists
            existing = await self.db.execute(
                select(GroupPermission)
                .where(GroupPermission.group_id == group_id)
                .where(GroupPermission.permission_id == permission_id)
                .where(GroupPermission.is_deleted == False)
            )
            
            if existing.scalar_one_or_none():
                raise ValueError("Permission already assigned to group")
            
            group_permission = GroupPermission(
                id=str(uuid.uuid4()),
                group_id=group_id,
                permission_id=permission_id,
                granted_by=granted_by,
                conditions=conditions,
                created_by=granted_by,
                created_at=datetime.utcnow()
            )
            
            self.db.add(group_permission)
            await self.db.commit()
            await self.db.refresh(group_permission)
            
            logger.info(f"Assigned permission {permission_id} to group {group_id}")
            return group_permission
            
        except Exception as e:
            logger.error(f"Failed to assign permission to group: {e}")
            await self.db.rollback()
            raise
    
    async def revoke_permission_from_group(
        self,
        group_id: str,
        permission_id: str,
        revoked_by: Optional[str] = None
    ) -> bool:
        """Revoke permission from group"""
        try:
            result = await self.db.execute(
                select(GroupPermission)
                .where(GroupPermission.group_id == group_id)
                .where(GroupPermission.permission_id == permission_id)
                .where(GroupPermission.is_deleted == False)
            )
            
            group_permission = result.scalar_one_or_none()
            if not group_permission:
                return False
            
            group_permission.soft_delete()
            if revoked_by:
                group_permission.updated_by = revoked_by
            
            await self.db.commit()
            
            logger.info(f"Revoked permission {permission_id} from group {group_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to revoke permission from group: {e}")
            await self.db.rollback()
            raise
    
    async def get_group_permissions(self, group_id: str) -> List[GroupPermission]:
        """Get all permissions for a group"""
        try:
            result = await self.db.execute(
                select(GroupPermission)
                .options(joinedload(GroupPermission.permission))
                .where(GroupPermission.group_id == group_id)
                .where(GroupPermission.is_deleted == False)
            )
            return result.scalars().all()
            
        except Exception as e:
            logger.error(f"Failed to get group permissions: {e}")
            return []

    # ==================== USER GROUP MEMBERSHIP CRUD OPERATIONS ====================
    
    async def add_user_to_group(
        self,
        user_id: str,
        group_id: str,
        added_by: Optional[str] = None,
        role_in_group: str = "MEMBER",
        expires_at: Optional[datetime] = None
    ) -> UserGroupMembership:
        """Add user to group"""
        try:
            # Check if membership already exists
            existing = await self.db.execute(
                select(UserGroupMembership)
                .where(UserGroupMembership.user_id == user_id)
                .where(UserGroupMembership.group_id == group_id)
                .where(UserGroupMembership.is_deleted == False)
            )
            
            if existing.scalar_one_or_none():
                raise ValueError("User already member of group")
            
            membership = UserGroupMembership(
                id=str(uuid.uuid4()),
                user_id=user_id,
                group_id=group_id,
                added_by=added_by,
                role_in_group=role_in_group,
                expires_at=expires_at,
                created_by=added_by,
                created_at=datetime.utcnow()
            )
            
            self.db.add(membership)
            await self.db.commit()
            await self.db.refresh(membership)
            
            logger.info(f"Added user {user_id} to group {group_id}")
            return membership
            
        except Exception as e:
            logger.error(f"Failed to add user to group: {e}")
            await self.db.rollback()
            raise
    
    async def remove_user_from_group(
        self,
        user_id: str,
        group_id: str,
        removed_by: Optional[str] = None
    ) -> bool:
        """Remove user from group"""
        try:
            result = await self.db.execute(
                select(UserGroupMembership)
                .where(UserGroupMembership.user_id == user_id)
                .where(UserGroupMembership.group_id == group_id)
                .where(UserGroupMembership.is_deleted == False)
            )
            
            membership = result.scalar_one_or_none()
            if not membership:
                return False
            
            membership.soft_delete()
            if removed_by:
                membership.updated_by = removed_by
            
            await self.db.commit()
            
            logger.info(f"Removed user {user_id} from group {group_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to remove user from group: {e}")
            await self.db.rollback()
            raise
    
    async def update_user_group_membership(
        self,
        user_id: str,
        group_id: str,
        role_in_group: Optional[str] = None,
        expires_at: Optional[datetime] = None,
        updated_by: Optional[str] = None
    ) -> Optional[UserGroupMembership]:
        """Update user group membership"""
        try:
            result = await self.db.execute(
                select(UserGroupMembership)
                .where(UserGroupMembership.user_id == user_id)
                .where(UserGroupMembership.group_id == group_id)
                .where(UserGroupMembership.is_deleted == False)
            )
            
            membership = result.scalar_one_or_none()
            if not membership:
                return None
            
            if role_in_group:
                membership.role_in_group = role_in_group
            if expires_at is not None:
                membership.expires_at = expires_at
            if updated_by:
                membership.updated_by = updated_by
            
            membership.updated_at = datetime.utcnow()
            
            await self.db.commit()
            await self.db.refresh(membership)
            
            logger.info(f"Updated membership for user {user_id} in group {group_id}")
            return membership
            
        except Exception as e:
            logger.error(f"Failed to update user group membership: {e}")
            await self.db.rollback()
            raise
    
    async def get_user_group_memberships(self, user_id: str) -> List[UserGroupMembership]:
        """Get all group memberships for a user"""
        try:
            result = await self.db.execute(
                select(UserGroupMembership)
                .options(joinedload(UserGroupMembership.group))
                .where(UserGroupMembership.user_id == user_id)
                .where(UserGroupMembership.is_deleted == False)
            )
            return result.scalars().all()
            
        except Exception as e:
            logger.error(f"Failed to get user group memberships: {e}")
            return []
    
    async def get_group_members(self, group_id: str) -> List[UserGroupMembership]:
        """Get all members of a group"""
        try:
            result = await self.db.execute(
                select(UserGroupMembership)
                .options(joinedload(UserGroupMembership.user))
                .where(UserGroupMembership.group_id == group_id)
                .where(UserGroupMembership.is_deleted == False)
            )
            return result.scalars().all()
            
        except Exception as e:
            logger.error(f"Failed to get group members: {e}")
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
    
