"""
ValidatePermission Service
Specialized for validating permissions in middleware 
Check permissions from database with support role hierarchy
"""
from typing import List, Dict, Any, Optional, Set
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import joinedload, selectinload

from models.database.user import User
from models.database.permission import (
    Permission, 
    Group, 
    UserPermission, 
    GroupPermission, 
    UserGroupMembership
)
from common.types import UserRole, RolePermissions
from utils.logging import get_logger

logger = get_logger(__name__)


class ValidatePermission:
    """
    Permission validation service for middleware
    Supports both specific permission checking and role hierarchy
    """
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    # ==================== CORE PERMISSION VALIDATION ====================
    
    async def check_user_has_permissions(
        self,
        user_id: str,
        required_permissions: List[str],
        user_role: str,
        require_all: bool = False
    ) -> Dict[str, Any]:
        """
        Check if user has required permissions
        Supports role hierarchy - higher roles inherit lower role permissions
        
        Args:
            user_id: User ID
            required_permissions: List of permission codes to check
            user_role: User's role from JWT token
            require_all: If True, user must have ALL permissions. If False, user needs ANY permission
        
        Returns:
            Dict with validation result
        """
        try:
            # Get user's actual permissions from database
            user_permissions = await self.get_user_permissions(user_id)
            
            # Get role-based permissions (for hierarchy support)
            role_permissions = self._get_role_permissions(user_role)
            
            # Combine user's direct/group permissions with role permissions
            all_user_permissions = set(user_permissions) | set(role_permissions)
            
            # Check if user has required permissions
            required_set = set(required_permissions)
            user_has_permissions = required_set & all_user_permissions
            
            if require_all:
                # User must have ALL required permissions
                has_access = required_set.issubset(all_user_permissions)
                missing_permissions = list(required_set - all_user_permissions)
            else:
                # User needs at least ONE of the required permissions
                has_access = len(user_has_permissions) > 0
                missing_permissions = list(required_set - all_user_permissions) if not has_access else []
            
            result = {
                "allowed": has_access,
                "user_permissions": list(all_user_permissions),
                "required_permissions": required_permissions,
                "matched_permissions": list(user_has_permissions),
                "missing_permissions": missing_permissions,
                "user_role": user_role,
                "require_all": require_all
            }
            
            if not has_access:
                if require_all:
                    result["reason"] = f"Missing required permissions: {missing_permissions}"
                else:
                    result["reason"] = f"User lacks any of the required permissions: {required_permissions}"
            
            logger.debug(
                f"Permission check for user {user_id}: {has_access} "
                f"(required: {required_permissions}, matched: {list(user_has_permissions)})"
            )
            
            return result
            
        except Exception as e:
            logger.error(f"Failed to check user permissions: {e}")
            return {
                "allowed": False,
                "reason": "Permission validation error",
                "error": str(e)
            }
    
    async def get_user_permissions(self, user_id: str) -> List[str]:
        """
        Get all permissions for a user from database (direct + group permissions)
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
                .where(User.is_deleted == False)
            )
            
            user = result.scalar_one_or_none()
            if not user:
                logger.warning(f"User {user_id} not found or inactive")
                return []
            
            permissions = set()
            
            # Add direct user permissions
            for user_perm in user.permissions:
                if not user_perm.is_deleted and not user_perm.permission.is_deleted:
                    permissions.add(user_perm.permission.permission_code)
            
            # Add group permissions
            for membership in user.group_memberships:
                if membership.is_deleted:
                    continue
                    
                group = membership.group
                if group.is_deleted:
                    continue
                    
                for group_perm in group.permissions:
                    if not group_perm.is_deleted and not group_perm.permission.is_deleted:
                        permissions.add(group_perm.permission.permission_code)
            
            permission_list = list(permissions)
            logger.debug(f"User {user_id} has {len(permission_list)} database permissions")
            return permission_list
            
        except Exception as e:
            logger.error(f"Failed to get user permissions: {e}")
            return []
    
    def _get_role_permissions(self, user_role: str) -> List[str]:
        """
        Get permissions for a role based on role hierarchy
        Higher roles inherit permissions from lower roles
        """
        try:
            role_enum = UserRole(user_role)
            permissions = RolePermissions.get_permissions_for_role(role_enum)
            return [perm.value for perm in permissions]
        except (ValueError, AttributeError) as e:
            logger.warning(f"Invalid user role {user_role}: {e}")
            return []
    
    # ==================== ROLE HIERARCHY VALIDATION ====================
    
    async def check_role_hierarchy(
        self,
        user_role: str,
        required_role: str
    ) -> bool:
        """
        Check if user role is sufficient based on hierarchy
        MAINTAINER > ADMIN > DEPT_ADMIN > DEPT_MANAGER > USER
        """
        role_hierarchy = {
            "MAINTAINER": 5,
            "ADMIN": 4,
            "DEPT_ADMIN": 3,
            "DEPT_MANAGER": 2,
            "USER": 1
        }
        
        user_level = role_hierarchy.get(user_role, 0)
        required_level = role_hierarchy.get(required_role, 0)
        
        return user_level >= required_level
    
    # ==================== CONTEXT VALIDATION ====================
    
    async def validate_context_access(
        self,
        user_id: str,
        user_role: str,
        tenant_id: Optional[str] = None,
        department_id: Optional[str] = None,
        required_context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Validate access based on user context
        """
        try:
            # Basic context validations
            if required_context:
                if required_context.get("requires_department") and not department_id:
                    if user_role not in ["MAINTAINER", "ADMIN"]:
                        return {
                            "allowed": False,
                            "reason": "Department assignment required"
                        }
                
                if required_context.get("requires_tenant") and not tenant_id:
                    if user_role != "MAINTAINER":
                        return {
                            "allowed": False,
                            "reason": "Tenant assignment required"
                        }
            
            return {"allowed": True}
            
        except Exception as e:
            logger.error(f"Context validation failed: {e}")
            return {
                "allowed": False,
                "reason": "Context validation error",
                "error": str(e)
            }
    
    # ==================== UTILITY METHODS ====================
    
    async def get_available_permissions(self) -> List[Dict[str, Any]]:
        """
        Get all available permissions from database
        """
        try:
            result = await self.db.execute(
                select(Permission)
                .where(Permission.is_deleted == False)
                .order_by(Permission.resource_type, Permission.action)
            )
            
            permissions = result.scalars().all()
            
            return [
                {
                    "permission_code": perm.permission_code,
                    "permission_name": perm.permission_name,
                    "resource_type": perm.resource_type,
                    "action": perm.action,
                    "description": perm.description,
                    "is_system": perm.is_system
                }
                for perm in permissions
            ]
            
        except Exception as e:
            logger.error(f"Failed to get available permissions: {e}")
            return []