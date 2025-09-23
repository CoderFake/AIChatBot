"""
Permission Service
Core permission management: create default groups and validate user permissions
"""
from typing import List, Dict, Any, Optional, Set
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
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
    DefaultGroupNames,
    UserRole,
    AccessLevel,
    DBDocumentPermissionLevel,
    DocumentConstants,
    ROLE_LEVEL,
)
from config.settings import get_settings
from utils.logging import get_logger
from services.cache.cache_manager import cache_manager
from utils.datetime_utils import DateTimeManager
from models.database.tenant import Department, Tenant

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

    # ==================== ROLE HIERARCHY HELPERS ====================

    async def get_user_roles(self, user_id: str) -> List[UserRole]:
        """Return tenant default roles that user currently holds (as UserRole enums)."""
        try:
            result = await self.db.execute(
                select(UserGroupMembership)
                .options(joinedload(UserGroupMembership.group))
                .where(UserGroupMembership.user_id == user_id)
                .where(UserGroupMembership.is_deleted == False)
            )
            memberships = result.scalars().all()
            roles: Set[UserRole] = set()
            for m in memberships:
                if m.group and m.group.group_code:
                    for role in UserRole:
                        if m.group.group_code.endswith(f"_{role.name}"):
                            roles.add(role)
                            break
            return list(roles)
        except Exception as e:
            logger.error(f"Failed to get roles for user {user_id}: {e}")
            return []

    def role_controls_role(self, actor_role: UserRole, target_role: UserRole) -> bool:
        """A role controls another if its permission set is a superset of the other's."""
        try:
            actor_perms = RolePermissions.get_permissions_for_role(actor_role)
            target_perms = RolePermissions.get_permissions_for_role(target_role)
            return actor_perms.issuperset(target_perms)
        except Exception as e:
            logger.error(f"Failed to evaluate role control {actor_role} -> {target_role}: {e}")
            return False

    async def can_user_control_user(self, actor_user_id: str, target_user_id: str) -> bool:
        """True if any actor role controls any target role by permission superset."""
        try:
            actor_roles = await self.get_user_roles(actor_user_id)
            target_roles = await self.get_user_roles(target_user_id)
            if not actor_roles or not target_roles:
                return False
            return any(self.role_controls_role(a, t) for a in actor_roles for t in target_roles)
        except Exception as e:
            logger.error(f"Failed to evaluate control between {actor_user_id} and {target_user_id}: {e}")
            return False

    async def can_user_control_group(self, actor_user_id: str, group_id: str) -> bool:
        """True if actor has a role whose permissions superset the target group's implied role."""
        try:
            actor_roles = await self.get_user_roles(actor_user_id)
            if not actor_roles:
                return False
            result = await self.db.execute(select(Group).where(Group.id == group_id))
            group = result.scalar_one_or_none()
            if not group or not group.group_code:
                return False
            target_role: Optional[UserRole] = None
            for role in UserRole:
                if group.group_code.endswith(f"_{role.name}"):
                    target_role = role
                    break
            if not target_role:
                return False
            return any(self.role_controls_role(a, target_role) for a in actor_roles)
        except Exception as e:
            logger.error(f"Failed to evaluate control over group {group_id}: {e}")
            return False

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
                created_at=await DateTimeManager.tenant_now_cached(None, self.db)
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
            
            permission.updated_at = await DateTimeManager.tenant_now_cached(None, self.db)
            
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
        tenant_id: Optional[str] = None,
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
                tenant_id=tenant_id,
                is_system=is_system,
                settings=settings,
                created_by=created_by,
                created_at=await DateTimeManager.tenant_now_cached(tenant_id or (await self._get_tenant_id_from_department(department_id)) if department_id else None, self.db)
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
        tenant_id: Optional[str] = None,
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
            if tenant_id:
                query = query.where(Group.tenant_id == tenant_id)
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
            
            tenant_id_for_group: Optional[str] = group.tenant_id
            if not tenant_id_for_group and group.department_id:
                tenant_id_for_group = await self._get_tenant_id_from_department(group.department_id)
            group.updated_at = await DateTimeManager.tenant_now_cached(tenant_id_for_group, self.db)
            
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
            
            await self._invalidate_group_members_permission_cache(group_id)
            
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
                created_at=await DateTimeManager.tenant_now_cached(await self._get_tenant_id_from_user(user_id), self.db)
            )
            
            self.db.add(user_permission)
            await self.db.commit()
            await self.db.refresh(user_permission)
            
            await self._invalidate_user_permission_cache(user_id)
            
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
            
            await self._invalidate_user_permission_cache(user_id)
            
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
                created_at=await DateTimeManager.tenant_now_cached(await self._get_tenant_id_from_group(group_id), self.db)
            )
            
            self.db.add(group_permission)
            await self.db.commit()
            await self.db.refresh(group_permission)
            
            await self._invalidate_group_members_permission_cache(group_id)
            
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
            
            await self._invalidate_group_members_permission_cache(group_id)
            
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
                created_at=await DateTimeManager.tenant_now_cached(await self._get_tenant_id_from_user(user_id), self.db)
            )
            
            self.db.add(membership)
            await self.db.commit()
            await self.db.refresh(membership)
            
            await self._invalidate_user_permission_cache(user_id)
            
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
            
            await self._invalidate_user_permission_cache(user_id)
            
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
            
            membership.updated_at = await DateTimeManager.tenant_now_cached(await self._get_tenant_id_from_user(user_id), self.db)
            
            await self.db.commit()
            await self.db.refresh(membership)
            
            await self._invalidate_user_permission_cache(user_id)
            
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
    
    # ==================== USER PERMISSIONS LOADING ====================

    async def get_user_effective_permissions(self, user_id: str) -> List[Dict[str, Any]]:
        """
        Get all effective permissions for a user (direct + group permissions)
        Returns: List of permission dictionaries with id, permission_code, permission_name, resource_type, action
        """
        try:
            # Validate user_id is a valid UUID
            try:
                uuid.UUID(user_id)
            except (ValueError, TypeError):
                logger.warning(f"Invalid user_id format: {user_id}. Cannot get effective permissions.")
                return []

            result = await self.db.execute(
                select(User)
                .options(
                    selectinload(User.permissions).joinedload(UserPermission.permission),
                    selectinload(User.group_memberships).joinedload(UserGroupMembership.group)
                    .selectinload(Group.permissions).joinedload(GroupPermission.permission)
                )
                .where(User.id == user_id)
                .where(User.is_active == True)
                .where(User.is_deleted == False)
            )
            user = result.scalar_one_or_none()

            if not user:
                logger.warning(f"User {user_id} not found or inactive for permissions loading")
                return []

            permission_set = set()
            permission_list = []

            # Direct user permissions
            if user.permissions:
                for user_perm in user.permissions:
                    if user_perm.is_deleted or not user_perm.permission:
                        continue

                    perm_key = user_perm.permission.id
                    if perm_key not in permission_set:
                        permission_set.add(perm_key)
                        permission_list.append({
                            "id": str(user_perm.permission.id),
                            "permission_code": user_perm.permission.permission_code,
                            "permission_name": user_perm.permission.permission_name,
                            "resource_type": user_perm.permission.resource_type,
                            "action": user_perm.permission.action,
                            "source": "direct"
                        })

            # Group permissions
            if user.group_memberships:
                for membership in user.group_memberships:
                    if membership.is_deleted or not membership.group:
                        continue

                    if membership.group.permissions:
                        for group_perm in membership.group.permissions:
                            if group_perm.is_deleted or not group_perm.permission:
                                continue

                            perm_key = group_perm.permission.id
                            if perm_key not in permission_set:
                                permission_set.add(perm_key)
                                permission_list.append({
                                    "id": str(group_perm.permission.id),
                                    "permission_code": group_perm.permission.permission_code,
                                    "permission_name": group_perm.permission.permission_name,
                                    "resource_type": group_perm.permission.resource_type,
                                    "action": group_perm.permission.action,
                                    "source": "group"
                                })

            logger.debug(f"Loaded {len(permission_list)} effective permissions for user {user_id}")
            return permission_list

        except Exception as e:
            logger.error(f"Failed to get effective permissions for user {user_id}: {e}")
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
            
            tz_now = await DateTimeManager.tenant_now_cached(tenant_id, self.db)

            for group_code, group_name, group_type in groups_to_create:
                group = Group(
                    id=str(uuid.uuid4()),
                    group_code=f"{tenant_id}_{group_code}",
                    group_name=group_name,
                    description=DefaultGroupNames.DESCRIPTIONS.get(group_name, f"Default {group_name} group"),
                    group_type=group_type,
                    tenant_id=tenant_id,
                    is_system=True,
                    created_at=tz_now
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
            
            tz_now = await DateTimeManager.tenant_now_cached(tenant_id, self.db)

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
                                created_at=tz_now
                            )
                            self.db.add(group_permission)
            
            logger.info(f"Setup default permissions for tenant {tenant_id}")
            
        except Exception as e:
            logger.error(f"Failed to setup default permissions: {e}")
            raise
    
    async def _invalidate_user_permission_cache(self, user_id: str) -> None:
        """Invalidate cached effective permissions for a user (scoped by tenant)."""
        try:
            try:
                uuid.UUID(user_id)
            except (ValueError, TypeError):
                logger.debug(f"Invalid user_id format: {user_id}. Skipping cache invalidation.")
                return

            result = await self.db.execute(select(User.tenant_id).where(User.id == user_id))
            row = result.first()
            if not row or not row[0]:
                return
            tenant_id = str(row[0])
            cache_key = f"tenant:{tenant_id}:user_permissions:{user_id}"
            await cache_manager.delete(cache_key)
            logger.debug(f"Invalidated user permission cache: {cache_key}")
        except Exception as e:
            logger.warning(f"Failed to invalidate user permission cache for {user_id}: {e}")
    
    async def _invalidate_group_members_permission_cache(self, group_id: str) -> None:
        """Invalidate cached permissions for all users in a group."""
        try:
            result = await self.db.execute(
                select(UserGroupMembership.user_id, User.tenant_id)
                .join(User, User.id == UserGroupMembership.user_id)
                .where(UserGroupMembership.group_id == group_id)
                .where(UserGroupMembership.is_deleted == False)
                .where(User.is_deleted == False)
            )
            rows = result.all()
            for user_id, tenant_id in rows:
                if tenant_id:
                    cache_key = f"tenant:{tenant_id}:user_permissions:{user_id}"
                    await cache_manager.delete(cache_key)
                    logger.debug(f"Invalidated user permission cache: {cache_key}")
        except Exception as e:
            logger.warning(f"Failed to invalidate group members cache for group {group_id}: {e}")

    async def _get_tenant_id_from_user(self, user_id: str) -> Optional[str]:
        try:
            try:
                uuid.UUID(user_id)
            except (ValueError, TypeError):
                logger.debug(f"Invalid user_id format: {user_id}. Cannot get tenant_id.")
                return None

            result = await self.db.execute(select(User.tenant_id).where(User.id == user_id))
            row = result.first()
            return str(row[0]) if row and row[0] else None
        except Exception:
            return None

    async def _get_tenant_id_from_group(self, group_id: str) -> Optional[str]:
        try:
            result = await self.db.execute(
                select(Department.tenant_id)
                .select_from(Group)
                .join(Department, Department.id == Group.department_id, isouter=True)
                .where(Group.id == group_id)
            )
            row = result.first()
            return str(row[0]) if row and row[0] else None
        except Exception:
            return None

    async def _get_tenant_id_from_department(self, department_id: str) -> Optional[str]:
        try:
            result = await self.db.execute(select(Department.tenant_id).where(Department.id == department_id))
            row = result.first()
            return str(row[0]) if row and row[0] else None
        except Exception:
            return None


class RAGPermissionService:
    """
    Specialized service for RAG (Retrieval-Augmented Generation) permission validation
    Handles access control for document collections based on user roles and department access
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def check_rag_access_permission(
        self,
        user_id: str,
        department_name: str,
        requested_access_level: str
    ) -> tuple[bool, List[str], str]:
        """
        Determine accessible RAG collections for a user and department.

        ADMIN/MAINTAINER -> full access (public/private) for any department.
        DEPT_ADMIN/DEPT_MANAGER -> public for any department, private only for their own department.
        USER -> public collections only.
        """
        try:
            # Validate user_id is a valid UUID
            try:
                uuid.UUID(user_id)
            except (ValueError, TypeError):
                logger.warning(f"Invalid user_id format: {user_id}. Cannot perform RAG access check.")
                return False, [], AccessLevel.PUBLIC.value

            if requested_access_level not in [AccessLevel.PUBLIC.value, AccessLevel.PRIVATE.value]:
                logger.warning(
                    f"Unsupported requested access level '{requested_access_level}' for user {user_id}; falling back to public"
                )
                return False, [], AccessLevel.PUBLIC.value

            user_result = await self.db.execute(
                select(User)
                .options(
                    selectinload(User.group_memberships).joinedload(UserGroupMembership.group),
                    selectinload(User.department),
                )
                .where(User.id == user_id)
                .where(User.is_active == True)
                .where(User.is_deleted == False)
            )
            user = user_result.scalar_one_or_none()

            if not user or not user.tenant_id:
                logger.warning(f"User {user_id} not found or inactive for RAG access check")
                return False, [], AccessLevel.PUBLIC.value

            resolved_roles: Set[UserRole] = set()
            if user.role:
                try:
                    resolved_roles.add(UserRole(user.role))
                except ValueError:
                    logger.debug(f"User {user_id} has unsupported role value '{user.role}'")

            for membership in user.group_memberships:
                if membership.is_deleted:
                    continue
                group = membership.group
                if not group or not group.group_code:
                    continue
                if "_MAINTAINER" in group.group_code:
                    resolved_roles.add(UserRole.MAINTAINER)
                elif "_ADMIN" in group.group_code:
                    resolved_roles.add(UserRole.ADMIN)
                elif "_DEPT_ADMIN" in group.group_code:
                    resolved_roles.add(UserRole.DEPT_ADMIN)
                elif "_DEPT_MANAGER" in group.group_code:
                    resolved_roles.add(UserRole.DEPT_MANAGER)

            if not resolved_roles:
                resolved_roles.add(UserRole.USER)

            highest_role = max(resolved_roles, key=lambda role: ROLE_LEVEL.get(role.value, 0))

            dept_result = await self.db.execute(
                select(Department)
                .where(Department.tenant_id == user.tenant_id)
                .where(Department.department_name == department_name)
                .where(Department.is_active == True)
            )
            department = dept_result.scalar_one_or_none()

            if not department:
                logger.warning(
                    f"Department {department_name} not found for tenant {user.tenant_id} when checking RAG access for user {user_id}"
                )
                return False, [], AccessLevel.PUBLIC.value

            department_id = str(department.id)
            public_collection = DocumentConstants.public_collection_name(department_id)
            private_collection = DocumentConstants.private_collection_name(department_id)

            if highest_role in {UserRole.MAINTAINER, UserRole.ADMIN}:
                if requested_access_level == AccessLevel.PUBLIC.value:
                    return True, [public_collection], AccessLevel.PUBLIC.value
                return True, [private_collection], AccessLevel.PRIVATE.value

            if highest_role in {UserRole.DEPT_ADMIN, UserRole.DEPT_MANAGER}:
                if requested_access_level == AccessLevel.PUBLIC.value:
                    return True, [public_collection], AccessLevel.PUBLIC.value

                user_department_id = str(user.department_id) if user.department_id else None
                if user_department_id and user_department_id == department_id:
                    return True, [private_collection], AccessLevel.PRIVATE.value

                logger.info(
                    f"User {user_id} with role {highest_role.value} denied private access to department {department_name}"
                )
                return False, [], AccessLevel.PUBLIC.value

            if requested_access_level == AccessLevel.PUBLIC.value:
                return True, [public_collection], AccessLevel.PUBLIC.value

            logger.info(f"User {user_id} denied private access due to insufficient role: {highest_role.value}")
            return False, [], AccessLevel.PUBLIC.value

        except Exception as e:
            logger.error(f"Failed to check RAG access for user {user_id}: {e}")
            return False, [], AccessLevel.PUBLIC.value

    async def check_rag_access_with_override(
        self,
        user_id: str,
        department_name: str,
        requested_access_level: str,
        access_scope_override: Optional[str] = None,
        admin_cross_department_access: bool = False
    ) -> tuple[bool, List[str], str]:
        """
        Check RAG access permission with optional access scope override

        Args:
            user_id: User ID
            department_name: Department name
            requested_access_level: Original requested access level
            access_scope_override: Override scope ('public', 'private', 'both', or None)
            admin_cross_department_access: If True, admin can access all departments

        Returns:
            (has_access, accessible_collections, effective_access_level)
        """
        try:
            try:
                uuid.UUID(user_id)
            except (ValueError, TypeError):
                logger.warning(f"Invalid user_id format: {user_id}. Cannot perform RAG access check.")
                return False, [], AccessLevel.PUBLIC.value
            from sqlalchemy import select

            normalized_department = (department_name or "").strip()
            normalized_override = access_scope_override.lower() if isinstance(access_scope_override, str) else None

            user_result = await self.db.execute(
                select(User)
                .options(
                    selectinload(User.group_memberships).joinedload(UserGroupMembership.group),
                    selectinload(User.department),
                )
                .where(User.id == user_id)
                .where(User.is_active == True)
                .where(User.is_deleted == False)
            )
            user = user_result.scalar_one_or_none()

            if not user or not user.tenant_id:
                return False, [], AccessLevel.PUBLIC.value

            resolved_roles: Set[UserRole] = set()
            if user.role:
                try:
                    resolved_roles.add(UserRole(user.role))
                except ValueError:
                    logger.debug(f"User {user_id} has unsupported role value '{user.role}'")

            for membership in user.group_memberships:
                if membership.is_deleted:
                    continue
                group = membership.group
                if not group or not group.group_code:
                    continue
                if "_MAINTAINER" in group.group_code:
                    resolved_roles.add(UserRole.MAINTAINER)
                elif "_ADMIN" in group.group_code:
                    resolved_roles.add(UserRole.ADMIN)
                elif "_DEPT_ADMIN" in group.group_code:
                    resolved_roles.add(UserRole.DEPT_ADMIN)
                elif "_DEPT_MANAGER" in group.group_code:
                    resolved_roles.add(UserRole.DEPT_MANAGER)

            if not resolved_roles:
                resolved_roles.add(UserRole.USER)

            highest_role = max(resolved_roles, key=lambda role: ROLE_LEVEL.get(role.value, 0))
            tenant_id = str(user.tenant_id)

            should_expand_cross_department = admin_cross_department_access
            if highest_role in {UserRole.ADMIN, UserRole.MAINTAINER}:
                if normalized_override == "both" or not normalized_department:
                    should_expand_cross_department = True
                elif normalized_department.lower() in {"all", "both", "*", "any"}:
                    should_expand_cross_department = True

            if should_expand_cross_department and tenant_id:
                effective_request = requested_access_level
                if normalized_override == "both" and effective_request not in [AccessLevel.PUBLIC.value, AccessLevel.PRIVATE.value, "both"]:
                    effective_request = "both"
                return await self.check_admin_rag_access_all_departments(
                    user_id,
                    tenant_id,
                    effective_request
                )

            if normalized_override:
                if normalized_override == "public":
                    return await self._get_public_access_only(user_id, normalized_department)
                if normalized_override == "private":
                    return await self._get_private_access_only(user_id, normalized_department)
                if normalized_override == "both":
                    return await self._get_both_access(user_id, normalized_department)
                logger.warning(f"Invalid access_scope_override: {access_scope_override}")
                return await self.check_rag_access_permission(user_id, normalized_department, requested_access_level)

            return await self.check_rag_access_permission(user_id, normalized_department, requested_access_level)

        except Exception as e:
            logger.error(f"Failed to check RAG access with override for user {user_id}: {e}")
            return True, [], AccessLevel.PUBLIC.value

    async def _get_public_access_only(self, user_id: str, department_name: str) -> tuple[bool, List[str], str]:
        """Get public access only, regardless of user permissions"""
        try:
            from sqlalchemy import select

            try:
                uuid.UUID(user_id)
            except (ValueError, TypeError):
                logger.warning(f"Invalid user_id format: {user_id}. Cannot get public access only.")
                return False, [], AccessLevel.PUBLIC.value

            # Get user to find tenant
            user_result = await self.db.execute(
                select(User).where(User.id == user_id)
            )
            user = user_result.scalar_one_or_none()

            if not user:
                return False, [], AccessLevel.PUBLIC.value

            # Get department
            dept_result = await self.db.execute(
                select(Department)
                .where(Department.tenant_id == user.tenant_id)
                .where(Department.department_name == department_name)
                .where(Department.is_active == True)
            )
            department = dept_result.scalar_one_or_none()

            if not department:
                return False, [], AccessLevel.PUBLIC.value

            # Return only public collection
            department_id = str(department.id)
            public_collection = DocumentConstants.public_collection_name(department_id)

            logger.info(f"Access scope override: User {user_id} forced to public access only")
            return True, [public_collection], AccessLevel.PUBLIC.value

        except Exception as e:
            logger.error(f"Failed to get public access only for user {user_id}: {e}")
            return False, [], AccessLevel.PUBLIC.value

    async def _get_private_access_only(self, user_id: str, department_name: str) -> tuple[bool, List[str], str]:
        """Get private access only if user has permission"""
        try:
            from sqlalchemy import select

            try:
                uuid.UUID(user_id)
            except (ValueError, TypeError):
                logger.warning(f"Invalid user_id format: {user_id}. Cannot get private access only.")
                return False, [], AccessLevel.PUBLIC.value

            user_result = await self.db.execute(
                select(User)
                .options(
                    selectinload(User.group_memberships).joinedload(UserGroupMembership.group),
                    selectinload(User.department),
                )
                .where(User.id == user_id)
                .where(User.is_active == True)
                .where(User.is_deleted == False)
            )
            user = user_result.scalar_one_or_none()

            if not user or not user.tenant_id:
                return False, [], AccessLevel.PUBLIC.value

            resolved_roles: Set[UserRole] = set()
            if user.role:
                try:
                    resolved_roles.add(UserRole(user.role))
                except ValueError:
                    logger.debug(f"User {user_id} has unsupported role value '{user.role}'")

            for membership in user.group_memberships:
                if membership.is_deleted:
                    continue
                group = membership.group
                if not group or not group.group_code:
                    continue
                if "_MAINTAINER" in group.group_code:
                    resolved_roles.add(UserRole.MAINTAINER)
                elif "_ADMIN" in group.group_code:
                    resolved_roles.add(UserRole.ADMIN)
                elif "_DEPT_ADMIN" in group.group_code:
                    resolved_roles.add(UserRole.DEPT_ADMIN)
                elif "_DEPT_MANAGER" in group.group_code:
                    resolved_roles.add(UserRole.DEPT_MANAGER)

            if not resolved_roles:
                resolved_roles.add(UserRole.USER)

            private_access_roles = {UserRole.DEPT_MANAGER, UserRole.DEPT_ADMIN, UserRole.ADMIN, UserRole.MAINTAINER}
            has_private_access = bool(resolved_roles & private_access_roles)

            dept_result = await self.db.execute(
                select(Department)
                .where(Department.tenant_id == user.tenant_id)
                .where(Department.department_name == department_name)
                .where(Department.is_active == True)
            )
            department = dept_result.scalar_one_or_none()

            if not department:
                return False, [], AccessLevel.PUBLIC.value

            department_id = str(department.id)

            if has_private_access:
                private_collection = DocumentConstants.private_collection_name(department_id)
                logger.info(f"Access scope override: User {user_id} forced to private access (has permission)")
                return True, [private_collection], AccessLevel.PRIVATE.value

            logger.warning(
                f"Access scope override: User {user_id} requested private but lacks permission; denying private access"
            )
            return False, [], AccessLevel.PUBLIC.value

        except Exception as e:
            logger.error(f"Failed to get private access only for user {user_id}: {e}")
            return False, [], AccessLevel.PUBLIC.value

    async def _get_both_access(self, user_id: str, department_name: str) -> tuple[bool, List[str], str]:
        """Get both public and private access if user has permission"""
        try:
            from sqlalchemy import select

            try:
                uuid.UUID(user_id)
            except (ValueError, TypeError):
                logger.warning(f"Invalid user_id format: {user_id}. Cannot get both access.")
                return False, [], AccessLevel.PUBLIC.value

            user_result = await self.db.execute(
                select(User)
                .options(
                    selectinload(User.group_memberships).joinedload(UserGroupMembership.group),
                    selectinload(User.department),
                )
                .where(User.id == user_id)
                .where(User.is_active == True)
                .where(User.is_deleted == False)
            )
            user = user_result.scalar_one_or_none()

            if not user or not user.tenant_id:
                return False, [], AccessLevel.PUBLIC.value

            resolved_roles: Set[UserRole] = set()
            if user.role:
                try:
                    resolved_roles.add(UserRole(user.role))
                except ValueError:
                    logger.debug(f"User {user_id} has unsupported role value '{user.role}'")

            for membership in user.group_memberships:
                if membership.is_deleted:
                    continue
                group = membership.group
                if not group or not group.group_code:
                    continue
                if "_MAINTAINER" in group.group_code:
                    resolved_roles.add(UserRole.MAINTAINER)
                elif "_ADMIN" in group.group_code:
                    resolved_roles.add(UserRole.ADMIN)
                elif "_DEPT_ADMIN" in group.group_code:
                    resolved_roles.add(UserRole.DEPT_ADMIN)
                elif "_DEPT_MANAGER" in group.group_code:
                    resolved_roles.add(UserRole.DEPT_MANAGER)

            if not resolved_roles:
                resolved_roles.add(UserRole.USER)

            private_access_roles = {UserRole.DEPT_MANAGER, UserRole.DEPT_ADMIN, UserRole.ADMIN, UserRole.MAINTAINER}
            has_private_access = bool(resolved_roles & private_access_roles)

            dept_result = await self.db.execute(
                select(Department)
                .where(Department.tenant_id == user.tenant_id)
                .where(Department.department_name == department_name)
                .where(Department.is_active == True)
            )
            department = dept_result.scalar_one_or_none()

            if not department:
                return False, [], AccessLevel.PUBLIC.value

            department_id = str(department.id)

            accessible_collections = []

            public_collection = DocumentConstants.public_collection_name(department_id)
            accessible_collections.append(public_collection)

            if has_private_access:
                private_collection = DocumentConstants.private_collection_name(department_id)
                accessible_collections.append(private_collection)
                logger.info(f"Access scope override: User {user_id} forced to both public+private access")
                return True, accessible_collections, "both"
            else:
                # Only public if no private permission
                logger.warning(f"Access scope override: User {user_id} requested both but no private permission, returning public only")
                return True, accessible_collections, AccessLevel.PUBLIC.value

        except Exception as e:
            logger.error(f"Failed to get both access for user {user_id}: {e}")
            return False, [], AccessLevel.PUBLIC.value

    async def get_user_accessible_collections(
        self,
        user_id: str,
        department_name: str
    ) -> Dict[str, Any]:
        """
        Get all collections user can access in a department
        Returns dict with public_collections, private_collections, and effective_permissions
        """
        try:
            public_access, public_collections, _ = await self.check_rag_access_permission(
                user_id=user_id,
                department_name=department_name,
                requested_access_level=AccessLevel.PUBLIC.value
            )

            private_access, private_collections, _ = await self.check_rag_access_permission(
                user_id=user_id,
                department_name=department_name,
                requested_access_level=AccessLevel.PRIVATE.value
            )

            return {
                "public_access": public_access,
                "public_collections": public_collections,
                "private_access": private_access,
                "private_collections": private_collections,
                "all_accessible_collections": list(set(public_collections + private_collections))
            }

        except Exception as e:
            logger.error(f"Failed to get user accessible collections for {user_id}: {e}")
            return {
                "public_access": False,
                "public_collections": [],
                "private_access": False,
                "private_collections": [],
                "all_accessible_collections": []
            }

    async def check_admin_rag_access_all_departments(
        self,
        user_id: str,
        tenant_id: str,
        requested_access_level: str
    ) -> tuple[bool, List[str], str]:
        """
        Check if admin user has access to ALL department collections
        Used for admin/maintainer users who need cross-department access

        Args:
            user_id: Admin user ID
            tenant_id: Tenant ID
            requested_access_level: Requested access level ('public', 'private', 'both')

        Returns:
            (has_access, accessible_collections, effective_access_level)
        """
        try:
            from sqlalchemy import select

            try:
                uuid.UUID(user_id)
            except (ValueError, TypeError):
                logger.warning(f"Invalid user_id format: {user_id}. Cannot check admin RAG access.")
                return False, [], AccessLevel.PUBLIC.value

            user_result = await self.db.execute(
                select(User)
                .options(selectinload(User.group_memberships).joinedload(UserGroupMembership.group))
                .where(User.id == user_id)
                .where(User.is_active == True)
                .where(User.is_deleted == False)
            )
            user = user_result.scalar_one_or_none()

            if not user:
                return False, [], AccessLevel.PUBLIC.value

            user_roles = set()
            for membership in user.group_memberships:
                if membership.is_deleted:
                    continue
                group = membership.group
                if group and group.group_code:
                    if "_ADMIN" in group.group_code:
                        user_roles.add(UserRole.ADMIN)
                    elif "_MAINTAINER" in group.group_code:
                        user_roles.add(UserRole.MAINTAINER)

            admin_roles = {UserRole.ADMIN, UserRole.MAINTAINER}
            dept_admin_roles = {UserRole.DEPT_ADMIN}
            is_admin = bool(user_roles & admin_roles)
            is_dept_admin = bool(user_roles & dept_admin_roles)

            if not (is_admin or is_dept_admin):
                logger.warning(f"User {user_id} is not admin/maintainer or dept_admin, cannot access all departments")
                return False, [], AccessLevel.PUBLIC.value

            user_department_id = None
            if is_dept_admin and not is_admin:
                user_dept_result = await self.db.execute(
                    select(User)
                    .options(selectinload(User.department))
                    .where(User.id == user_id)
                )
                user_with_dept = user_dept_result.scalar_one_or_none()
                if user_with_dept and user_with_dept.department:
                    user_department_id = str(user_with_dept.department.id)

            if is_admin:
                dept_result = await self.db.execute(
                    select(Department)
                    .where(Department.tenant_id == tenant_id)
                    .where(Department.is_active == True)
                )
                departments = dept_result.scalars().all()
            elif is_dept_admin and user_department_id:
                dept_result = await self.db.execute(
                    select(Department)
                    .where(Department.id == user_department_id)
                    .where(Department.tenant_id == tenant_id)
                    .where(Department.is_active == True)
                )
                departments = dept_result.scalars().all()
            else:
                logger.warning(f"Cannot determine accessible departments for user {user_id}")
                return False, [], AccessLevel.PUBLIC.value

            if not departments:
                logger.warning(f"No departments found for user {user_id} with tenant {tenant_id}")
                return False, [], AccessLevel.PUBLIC.value

            accessible_collections = []
            tenant_id_str = str(tenant_id)

            for department in departments:
                dept_id_str = str(department.id)

                if requested_access_level in [AccessLevel.PUBLIC.value, "both"]:
                    accessible_collections.append(
                        DocumentConstants.public_collection_name(dept_id_str)
                    )

                if requested_access_level in [AccessLevel.PRIVATE.value, "both"]:
                    accessible_collections.append(
                        DocumentConstants.private_collection_name(dept_id_str)
                    )

            effective_access_level = requested_access_level
            has_access = len(accessible_collections) > 0

            logger.info(f"Admin {user_id} granted access to {len(accessible_collections)} collections across {len(departments)} departments")
            return has_access, accessible_collections, effective_access_level

        except Exception as e:
            logger.error(f"Failed to check admin RAG access for user {user_id}: {e}")
            return False, [], AccessLevel.PUBLIC.value

