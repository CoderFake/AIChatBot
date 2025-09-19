"""
ValidatePermission Service
Specialized for validating permissions in middleware 
Check permissions from database with support role hierarchy
"""
from typing import List, Dict, Any, Optional
from enum import Enum as PyEnum
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from sqlalchemy.orm import selectinload

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
from services.cache.cache_manager import cache_manager

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
        required_permissions: List[Any],
        user_role: str,
        require_all: bool = False,
        tenant_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Check if user has required permissions
        Supports role hierarchy - higher roles inherit lower role permissions
        Uses cache per tenant-user for effective permissions
        Accepts permission codes as str or Enum (perm.value)
        """
        try:
            normalized_required = self._normalize_permission_codes(required_permissions)
            
            effective_permissions = await self._get_effective_permissions(user_id, user_role, tenant_id)
            all_user_permissions = set(effective_permissions)
            
            required_set = set(normalized_required)
            matched = required_set & all_user_permissions
            
            if require_all:
                has_access = required_set.issubset(all_user_permissions)
                missing_permissions = list(required_set - all_user_permissions)
            else:
                has_access = len(matched) > 0
                missing_permissions = list(required_set - all_user_permissions) if not has_access else []
            
            result = {
                "allowed": has_access,
                "user_permissions": list(all_user_permissions),
                "required_permissions": normalized_required,
                "matched_permissions": list(matched),
                "missing_permissions": missing_permissions,
                "user_role": user_role,
                "require_all": require_all
            }
            
            if not has_access:
                result["reason"] = (
                    f"Missing required permissions: {missing_permissions}" if require_all
                    else f"User lacks any of: {normalized_required}"
                )
            
            logger.debug(
                f"Permission check for user {user_id}: {has_access} "
                f"(required: {normalized_required}, matched: {list(matched)})"
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

            for user_perm in user.permissions:
                if not user_perm.is_deleted and not user_perm.permission.is_deleted:
                    permissions.add(user_perm.permission.permission_code)

            for membership in user.group_memberships:
                if membership.is_deleted:
                    continue
                group = membership.group
                if group.is_deleted:
                    continue

                if user.tenant_id and getattr(group, 'tenant_id', None) and str(group.tenant_id) != str(user.tenant_id):
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
    
    # ==================== PRIVATE CACHE HELPERS ====================
    
    async def _get_effective_permissions(
        self,
        user_id: str,
        user_role: str,
        tenant_id: Optional[str]
    ) -> List[str]:
        """Compute or fetch from cache the effective permission codes for a user within a tenant."""
        try:
            if user_role == UserRole.MAINTAINER.value:
                tenant_id = None
            if not tenant_id:
                res = await self.db.execute(select(User.tenant_id).where(User.id == user_id))
                row = res.first()
                if row and row[0]:
                    tenant_id = str(row[0])
            cache_key = f"tenant:{tenant_id}:user_permissions:{user_id}" if tenant_id else f"user_permissions:{user_id}"
            
            cached = await cache_manager.get(cache_key)
            if isinstance(cached, list):
                return cached
            
            db_perms = await self.get_user_permissions(user_id)
            role_perms = self._get_role_permissions(user_role)
            all_perms = sorted(set(db_perms) | set(role_perms))
            
            await cache_manager.set(cache_key, all_perms)
            return all_perms
        except Exception as e:
            logger.warning(f"Failed to build effective permissions cache for {user_id}: {e}")
            db_perms = await self.get_user_permissions(user_id)
            role_perms = self._get_role_permissions(user_role)
            return sorted(set(db_perms) | set(role_perms))
    
    def _normalize_permission_codes(self, codes: List[Any]) -> List[str]:
        """Normalize list of permission identifiers (Enum or str) to list of strings."""
        normalized: List[str] = []
        for c in codes:
            try:
                if isinstance(c, PyEnum):
                    normalized.append(str(c.value))
                else:
                    normalized.append(str(c))
            except Exception:
                normalized.append(str(c))
        return normalized

    # ==================== ROLE-BASED DATA ACCESS ====================
    
    async def get_tools_by_role_context(
        self,
        user_role: str,
        tenant_id: Optional[str] = None,
        department_id: Optional[str] = None,
        user_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get tools depending on role and context
        
        Args:
            user_role: MAINTAINER, ADMIN, DEPT_ADMIN, DEPT_MANAGER, USER
            tenant_id: ID of tenant
            department_id: ID of department  
            user_id: ID of user
            
        Returns:
            Dict with tools data suitable for role
        """
        try:
            if user_role == UserRole.MAINTAINER.value:
                return await self._get_maintainer_tools_view()
            
            elif user_role == UserRole.ADMIN.value and tenant_id:
                return await self._get_admin_tools_view(tenant_id)
            
            elif user_role in [UserRole.DEPT_ADMIN.value, UserRole.DEPT_MANAGER.value] and tenant_id and department_id:
                return await self._get_dept_admin_tools_view(tenant_id, department_id)
            
            elif tenant_id and department_id:
                return await self._get_user_tools_view(tenant_id, department_id, user_id)
            
            else:
                return {
                    "tools": [], 
                    "total": 0, 
                    "message": "Insufficient context for role",
                    "required_context": self._get_required_context_for_role(user_role)
                }
                
        except Exception as e:
            logger.error(f"Failed to get tools by role {user_role}: {e}")
            return {"tools": [], "total": 0, "error": str(e)}
    
    async def get_providers_by_role_context(
        self,
        user_role: str,
        tenant_id: Optional[str] = None,
        department_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get providers depending on role and context
        
        Args:
            user_role: Role of user
            tenant_id: ID of tenant
            department_id: ID of department
            
        Returns:
            Dict with providers data suitable for role
        """ 
        try:
            if user_role == UserRole.MAINTAINER.value:
                return await self._get_maintainer_providers_view()
            
            elif user_role == UserRole.ADMIN.value and tenant_id:
                return await self._get_admin_providers_view(tenant_id)
            
            elif tenant_id: 
                return await self._get_tenant_providers_view(tenant_id)
            
            else:
                return {
                    "providers": [], 
                    "total": 0, 
                    "message": "Tenant context required",
                    "required_context": ["tenant_id"]
                }
                
        except Exception as e:
            logger.error(f"Failed to get providers by role {user_role}: {e}")
            return {"providers": [], "total": 0, "error": str(e)}
    
    # ==================== TOOLS VIEW METHODS ====================
    
    async def _get_maintainer_tools_view(self) -> Dict[str, Any]:
        """MAINTAINER: Global view of all available tools"""
        from models.database.tool import Tool

        result = await self.db.execute(
            select(Tool)
            .where(Tool.is_enabled == True)
            .order_by(Tool.tool_name)
        )
        tools = result.scalars().all()

        tools_data = []
        for tool in tools:
            tools_data.append({
                "id": str(tool.id),
                "name": tool.tool_name,
                "description": tool.description,
                "category": tool.category,
                "is_enabled": tool.is_enabled,
                "is_system": tool.is_system,
                "created_at": tool.created_at.isoformat() if tool.created_at else None
            })

        return {"tools": tools_data, "total": len(tools_data), "scope": "global"}
    
    async def _get_admin_tools_view(self, tenant_id: str) -> Dict[str, Any]:
        """ADMIN: Tools of tenant with full config access"""
        from models.database.tool import Tool, TenantToolConfig
        
        result = await self.db.execute(
            select(TenantToolConfig)
            .join(Tool, Tool.id == TenantToolConfig.tool_id)
            .where(
                and_(
                    TenantToolConfig.tenant_id == tenant_id,
                    Tool.is_enabled == True
                )
            )
            .order_by(Tool.tool_name)
        )
        configs = result.scalars().all()
        
        tools_data = []
        for config in configs:
            tool = config.tool
            tools_data.append({
                "id": str(tool.id),
                "name": tool.tool_name,
                "description": tool.description,
                "category": tool.category,
                "is_enabled": config.is_enabled,
                "config_data": config.config_data or {},
                "usage_limits": {},
                "configured_by": str(config.configured_by) if config.configured_by else None,
                "configured_at": config.created_at.isoformat() if config.created_at else None,
                "can_modify_config": True,
                "can_enable_disable": True
            })
        
        return {
            "tools": tools_data, 
            "total": len(tools_data), 
            "tenant_id": tenant_id,
            "scope": "tenant"
        }
    
    async def _get_dept_admin_tools_view(self, tenant_id: str, department_id: str) -> Dict[str, Any]:
        """DEPT_ADMIN/DEPT_MANAGER: Tools of department with limited config"""
        from models.database.tool import Tool
        from models.database.agent import AgentToolConfig, Agent

        result = await self.db.execute(
            select(AgentToolConfig, Tool, Agent)
            .join(Tool, Tool.id == AgentToolConfig.tool_id)
            .join(Agent, Agent.id == AgentToolConfig.agent_id)
            .where(
                and_(
                    Agent.department_id == department_id,
                    Tool.is_enabled == True,
                    AgentToolConfig.is_enabled == True
                )
            )
            .order_by(Tool.tool_name)
        )
        agent_tool_configs = result.scalars().all()

        tools_data = []
        for agent_config, tool, agent in agent_tool_configs:
            tools_data.append({
                "id": str(tool.id),
                "name": tool.tool_name,
                "description": tool.description,
                "category": tool.category,
                "is_enabled": agent_config.is_enabled,
                "config_data": agent_config.config_data or {},
                "usage_limits": {},
                "configured_by": str(agent_config.configured_by) if agent_config.configured_by else None,
                "configured_at": agent_config.created_at.isoformat() if agent_config.created_at else None,
                "can_modify_config": True,
                "can_enable_disable": True
            })
        
        return {
            "tools": tools_data,
            "total": len(tools_data),
            "tenant_id": tenant_id,
            "department_id": department_id,
            "scope": "department"
        }
    
    async def _get_user_tools_view(self, tenant_id: str, department_id: str, user_id: Optional[str]) -> Dict[str, Any]:
        """USER: Only tools enabled and can be used""" 
        from models.database.tool import Tool
        from models.database.agent import AgentToolConfig, Agent

        result = await self.db.execute(
            select(AgentToolConfig, Tool, Agent)
            .join(Tool, Tool.id == AgentToolConfig.tool_id)
            .join(Agent, Agent.id == AgentToolConfig.agent_id)
            .where(
                and_(
                    Agent.department_id == department_id,
                    AgentToolConfig.is_enabled == True,
                    Tool.is_enabled == True
                )
            )
            .order_by(Tool.tool_name)
        )
        agent_tool_configs = result.scalars().all()

        tools_data = []
        for agent_config, tool, agent in agent_tool_configs:
            tools_data.append({
                "id": str(tool.id),
                "name": tool.tool_name,
                "description": tool.description,
                "category": tool.category,
                "is_enabled": True,
                "usage_limits": {},
                "can_modify_config": False,
                "can_enable_disable": False
            })
        
        return {
            "tools": tools_data,
            "total": len(tools_data),
            "tenant_id": tenant_id,
            "department_id": department_id,
            "scope": "user"
        }
    
    # ==================== PROVIDERS VIEW METHODS ====================
    
    async def _get_maintainer_providers_view(self) -> Dict[str, Any]:
        """MAINTAINER: All providers with models (global view)"""
        from models.database.provider import Provider, ProviderModel

        result = await self.db.execute(
            select(Provider)
            .where(Provider.is_enabled == True)
            .order_by(Provider.provider_name)
        )
        providers = result.scalars().all()

        providers_data = []
        for provider in providers:
            models_result = await self.db.execute(
                select(ProviderModel).where(
                    and_(
                        ProviderModel.provider_id == provider.id,
                        ProviderModel.is_enabled == True
                    )
                )
            )
            provider_models = models_result.scalars().all()
            models = [model.model_name for model in provider_models]

            providers_data.append({
                "id": str(provider.id),
                "provider_name": provider.provider_name,
                "models": models,
                "is_enabled": provider.is_enabled,
                "created_at": provider.created_at.isoformat() if provider.created_at else None
            })

        return {"providers": providers_data, "total": len(providers_data), "scope": "global"}
    
    async def _get_admin_providers_view(self, tenant_id: str) -> Dict[str, Any]:
        """ADMIN: Providers of tenant with config access"""
        from models.database.provider import Provider, ProviderModel, TenantProviderConfig

        result = await self.db.execute(
            select(TenantProviderConfig)
            .join(Provider, Provider.id == TenantProviderConfig.provider_id)
            .options(selectinload(TenantProviderConfig.provider).selectinload(Provider.models))
            .where(
                and_(
                    TenantProviderConfig.tenant_id == tenant_id,
                    Provider.is_enabled == True
                )
            )
            .order_by(Provider.provider_name)
        )
        configs = result.scalars().all()

        providers_data = []
        for config in configs:
            provider = config.provider

            models = [
                {"id": str(model.id), "model_name": model.model_name} 
                for model in provider.models if model.is_enabled
            ]

            providers_data.append({
                "id": str(provider.id),
                "provider_name": provider.provider_name,
                "models": models,
                "is_enabled": config.is_enabled,
                "api_keys_configured": bool(config.api_keys),
                "configured_by": str(config.configured_by) if config.configured_by else None,
                "configured_at": config.created_at.isoformat() if config.created_at else None,
                "can_modify_config": True,
                "can_manage_keys": True
            })

        return {
            "providers": providers_data,
            "total": len(providers_data),
            "tenant_id": tenant_id,
            "scope": "tenant"
        }
    
    async def _get_tenant_providers_view(self, tenant_id: str) -> Dict[str, Any]:
        """DEPT_ADMIN/DEPT_MANAGER/USER: Providers enabled for tenant (read-only)"""
        from models.database.provider import Provider, ProviderModel, TenantProviderConfig

        result = await self.db.execute(
            select(TenantProviderConfig)
            .join(Provider, Provider.id == TenantProviderConfig.provider_id)
            .options(selectinload(TenantProviderConfig.provider).selectinload(Provider.models))
            .where(
                and_(
                    TenantProviderConfig.tenant_id == tenant_id,
                    TenantProviderConfig.is_enabled == True,
                    Provider.is_enabled == True
                )
            )
            .order_by(Provider.provider_name)
        )
        configs = result.scalars().all()

        providers_data = []
        for config in configs:
            provider = config.provider

            models = [
                {"id": str(model.id), "model_name": model.model_name} 
                for model in provider.models if model.is_enabled
            ]

            providers_data.append({
                "id": str(provider.id),
                "provider_name": provider.provider_name,
                "models": models,
                "is_enabled": True,
                "api_keys_configured": bool(config.api_keys),
                "can_modify_config": False,
                "can_manage_keys": False
            })

        return {
            "providers": providers_data,
            "total": len(providers_data),
            "tenant_id": tenant_id,
            "scope": "read_only"
        }
    
    # ==================== HELPER METHODS ====================
    
    def _get_required_context_for_role(self, user_role: str) -> List[str]:
        """Get required context fields for role"""
        context_map = {
            UserRole.MAINTAINER.value: [],
            UserRole.ADMIN.value: ["tenant_id"],
            UserRole.DEPT_ADMIN.value: ["tenant_id", "department_id"],
            UserRole.DEPT_MANAGER.value: ["tenant_id", "department_id"],
            UserRole.USER.value: ["tenant_id", "department_id"]
        }
        return context_map.get(user_role, ["tenant_id", "department_id"])