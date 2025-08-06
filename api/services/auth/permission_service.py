from typing import List, Dict, Any, Optional, Set
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, delete
from sqlalchemy.orm import joinedload
from datetime import datetime
import uuid

from models.database.user import User, UserGroup, GroupPermission
from models.database.document import Document, DocumentCollection
from models.database.tenant import Tenant, Department
from models.database.tool import Tool, TenantToolConfig
from models.database.provider import LLMProvider, TenantProviderConfig
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
            
            # Setup default provider (Gemini)
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
            logger.error(f"Failed to create tenant with defaults: {e}")
            raise
    
    async def _create_default_groups(self, tenant_id: str) -> Dict[str, str]:
        """
        Create default user groups for tenant
        """
        groups = {}
        
        admin_group = UserGroup(
            id=str(uuid.uuid4()),
            tenant_id=tenant_id,
            group_name=DefaultGroupNames.ADMIN,
            description=DefaultGroupNames.DESCRIPTIONS[DefaultGroupNames.ADMIN],
            created_at=datetime.utcnow()
        )
        self.db.add(admin_group)
        groups["admin"] = admin_group.id
        
        dept_admin_group = UserGroup(
            id=str(uuid.uuid4()),
            tenant_id=tenant_id,
            group_name=DefaultGroupNames.DEPT_ADMIN,
            description=DefaultGroupNames.DESCRIPTIONS[DefaultGroupNames.DEPT_ADMIN],
            created_at=datetime.utcnow()
        )
        self.db.add(dept_admin_group)
        groups["dept_admin"] = dept_admin_group.id
        
        dept_manager_group = UserGroup(
            id=str(uuid.uuid4()),
            tenant_id=tenant_id,
            group_name=DefaultGroupNames.DEPT_MANAGER,
            description=DefaultGroupNames.DESCRIPTIONS[DefaultGroupNames.DEPT_MANAGER],
            created_at=datetime.utcnow()
        )
        self.db.add(dept_manager_group)
        groups["dept_manager"] = dept_manager_group.id
        
        user_group = UserGroup(
            id=str(uuid.uuid4()),
            tenant_id=tenant_id,
            group_name=DefaultGroupNames.USER,
            description=DefaultGroupNames.DESCRIPTIONS[DefaultGroupNames.USER],
            created_at=datetime.utcnow()
        )
        self.db.add(user_group)
        groups["user"] = user_group.id
        
        return groups
    
    async def _setup_default_permissions(
        self,
        tenant_id: str,
        groups: Dict[str, str]
    ):
        """
        Setup default permissions for each group using RolePermissions
        """
        admin_permissions = RolePermissions.get_permission_values_for_role(UserRole.ADMIN)
        for permission in admin_permissions:
            perm = GroupPermission(
                id=str(uuid.uuid4()),
                group_id=groups["admin"],
                permission_name=permission,
                created_at=datetime.utcnow()
            )
            self.db.add(perm)
        
        dept_admin_permissions = RolePermissions.get_permission_values_for_role(UserRole.DEPT_ADMIN)
        for permission in dept_admin_permissions:
            perm = GroupPermission(
                id=str(uuid.uuid4()),
                group_id=groups["dept_admin"],
                permission_name=permission,
                created_at=datetime.utcnow()
            )
            self.db.add(perm)
        
        dept_manager_permissions = RolePermissions.get_permission_values_for_role(UserRole.DEPT_MANAGER)
        for permission in dept_manager_permissions:
            perm = GroupPermission(
                id=str(uuid.uuid4()),
                group_id=groups["dept_manager"],
                permission_name=permission,
                created_at=datetime.utcnow()
            )
            self.db.add(perm)
        
        user_permissions = RolePermissions.get_permission_values_for_role(UserRole.USER)
        for permission in user_permissions:
            perm = GroupPermission(
                id=str(uuid.uuid4()),
                group_id=groups["user"],
                permission_name=permission,
                created_at=datetime.utcnow()
            )
            self.db.add(perm)
    
    async def _setup_default_tools(self, tenant_id: str):
        """
        Setup default tool access for tenant (all disabled by default)
        """
        result = await self.db.execute(select(Tool))
        tools = result.scalars().all()
        
        for tool in tools:
            config = TenantToolConfig(
                id=str(uuid.uuid4()),
                tool_id=tool.id,
                tenant_id=tenant_id,
                is_enabled=False, 
                config_data={},
                created_at=datetime.utcnow()
            )
            self.db.add(config)
    
    async def _setup_default_provider(self, tenant_id: str):
        """
        Setup default LLM provider (Gemini) for tenant
        """
        result = await self.db.execute(
            select(LLMProvider).where(
                LLMProvider.provider_name == DefaultProviderConfig.PROVIDER_NAME
            )
        )
        gemini_provider = result.scalar_one_or_none()
        
        if gemini_provider:
            config = TenantProviderConfig(
                id=str(uuid.uuid4()),
                tenant_id=tenant_id,
                provider_id=gemini_provider.id,
                is_enabled=True,
                config_data=DefaultProviderConfig.get_default_config(),
                is_default=True,
                created_at=datetime.utcnow()
            )
            self.db.add(config)
    
    async def get_user_permissions(
        self,
        user_id: str,
        tenant_id: Optional[str] = None
    ) -> Set[str]:
        """
        Get all permissions for a user based on their groups
        """
        try:
            query = select(UserGroup).join(
                User.groups
            ).where(User.id == user_id)
            
            if tenant_id:
                query = query.where(UserGroup.tenant_id == tenant_id)
            
            result = await self.db.execute(query)
            user_groups = result.scalars().all()
            
            permissions = set()
            for group in user_groups:
                group_perms_result = await self.db.execute(
                    select(GroupPermission).where(
                        GroupPermission.group_id == group.id
                    )
                )
                group_perms = group_perms_result.scalars().all()
                
                for perm in group_perms:
                    permissions.add(perm.permission_name)
            
            return permissions
            
        except Exception as e:
            logger.error(f"Failed to get user permissions: {e}")
            return set()
    
    async def check_permission(
        self,
        user_id: str,
        permission: str,
        tenant_id: Optional[str] = None
    ) -> bool:
        """
        Check if user has specific permission
        """
        user_permissions = await self.get_user_permissions(user_id, tenant_id)
        return permission in user_permissions
    
    async def assign_user_to_group(
        self,
        user_id: str,
        group_id: str
    ):
        """
        Assign user to a group
        """
        try:
            user_result = await self.db.execute(
                select(User).where(User.id == user_id)
            )
            user = user_result.scalar_one_or_none()
            
            group_result = await self.db.execute(
                select(UserGroup).where(UserGroup.id == group_id)
            )
            group = group_result.scalar_one_or_none()
            
            if user and group:
                user.groups.append(group)
                await self.db.commit()
                logger.info(f"Assigned user {user_id} to group {group_id}")
            
        except Exception as e:
            await self.db.rollback()
            logger.error(f"Failed to assign user to group: {e}")
            raise
    
    async def create_custom_group(
        self,
        tenant_id: str,
        group_name: str,
        description: str,
        permissions: List[str]
    ) -> str:
        """
        Create custom group with specific permissions
        """
        try:
            group = UserGroup(
                id=str(uuid.uuid4()),
                tenant_id=tenant_id,
                group_name=group_name,
                description=description,
                created_at=datetime.utcnow()
            )
            self.db.add(group)
            
            for permission_name in permissions:
                perm = GroupPermission(
                    id=str(uuid.uuid4()),
                    group_id=group.id,
                    permission_name=permission_name,
                    created_at=datetime.utcnow()
                )
                self.db.add(perm)
            
            await self.db.commit()
            logger.info(f"Created custom group {group_name} for tenant {tenant_id}")
            
            return group.id
            
        except Exception as e:
            await self.db.rollback()
            logger.error(f"Failed to create custom group: {e}")
            raise
    
    async def update_group_permissions(
        self,
        group_id: str,
        permissions: List[str]
    ):
        """
        Update permissions for a group
        """
        try:
            await self.db.execute(
                delete(GroupPermission).where(
                    GroupPermission.group_id == group_id
                )
            )
            
            for permission_name in permissions:
                perm = GroupPermission(
                    id=str(uuid.uuid4()),
                    group_id=group_id,
                    permission_name=permission_name,
                    created_at=datetime.utcnow()
                )
                self.db.add(perm)
            
            await self.db.commit()
            logger.info(f"Updated permissions for group {group_id}")
            
        except Exception as e:
            await self.db.rollback()
            logger.error(f"Failed to update group permissions: {e}")
            raise
    
    async def get_user_all_permissions(self, user_id: str) -> Dict[str, Any]:
        """
        Get complete user context with all permissions
        Used by auth middleware
        """
        try:
            result = await self.db.execute(
                select(User).where(User.id == user_id)
            )
            user = result.scalar_one_or_none()
            
            if not user:
                return None
            
            permissions = await self.get_user_permissions(user_id, user.tenant_id)
            
            return {
                "user_id": user.id,
                "username": user.username,
                "email": user.email,
                "role": user.role,
                "tenant_id": user.tenant_id,
                "department_id": user.department_id,
                "permissions": list(permissions),
                "is_active": user.is_active
            }
            
        except Exception as e:
            logger.error(f"Failed to get user context: {e}")
            return None

class RAGPermissionService:
    """
    Service for RAG permission management with collection access control
    """
    
    def __init__(self, db_session: AsyncSession):
        self.db = db_session
    
    async def check_rag_access_permission(
        self, 
        user_id: str, 
        department_name: str,
        requested_access_level: str = AccessLevel.PUBLIC.value
    ) -> Tuple[bool, List[str], str]:
        """
        Check user's RAG access permission and return accessible collections
        
        Args:
            user_id: User ID requesting access
            department_name: Department name for collection access
            requested_access_level: 'public' or 'private'
            
        Returns:
            Tuple of (has_access, accessible_collections, effective_access_level)
        """
        try:
            user_query = select(User).where(User.id == user_id)
            result = await self.db.execute(user_query)
            user = result.scalar_one_or_none()
            
            if not user:
                return False, [], AccessLevel.PUBLIC.value
            
            if user.role == UserRole.USER.value and not user.department_id:
                return True, [f"{department_name}_public"], AccessLevel.PUBLIC.value
            
            dept_query = select(Department).where(Department.id == user.department_id)
            dept_result = await self.db.execute(dept_query)
            user_department = dept_result.scalar_one_or_none()
            
            accessible_collections = []
            effective_access_level = AccessLevel.PUBLIC.value
            
            accessible_collections.append(f"{department_name}_public")
            
            has_private_access = await self._check_private_access(
                user, user_department, department_name, requested_access_level
            )
            
            if has_private_access:
                accessible_collections.append(f"{department_name}_private")
                effective_access_level = AccessLevel.PRIVATE.value
            
            return True, accessible_collections, effective_access_level
            
        except Exception as e:
            logger.error(f"Error checking RAG permission: {e}")
            return False, [], AccessLevel.PUBLIC.value
    
    async def _check_private_access(
        self, 
        user: User, 
        user_department: Optional[Department], 
        requested_dept: str,
        requested_access_level: str
    ) -> bool:
        """
        Check if user has private collection access
        """
        if user.role in [UserRole.MAINTAINER.value, UserRole.ADMIN.value]:
            return True
        
        if not user_department:
            return False
        
        if user_department.name == requested_dept:
            if user.role in [
                UserRole.ADMIN.value,
                UserRole.DEPT_ADMIN.value, 
                UserRole.DEPT_MANAGER.value
            ]:
                return True
            
            if (user.role == UserRole.USER.value and 
                requested_access_level == AccessLevel.PRIVATE.value):
                return True
        
        return False
    
    async def create_department_collections(
        self, 
        department_name: str, 
        department_id: str
    ) -> Dict[str, str]:
        """
        Create both public and private collections for a department
        
        Returns:
            Dict with collection names and their Milvus instances
        """
        try:
            collections_created = {}
            
            public_collection = DocumentCollection(
                department_id=department_id,
                collection_name=f"{department_name}_public",
                collection_type=DBDocumentPermissionLevel.PUBLIC.value,
                is_active=True,
                vector_config={
                    "embedding_model": "BAAI/bge-m3",
                    "vector_dim": 1024,
                    "index_type": "HNSW",
                    "metric_type": "IP"
                }
            )
            
            private_collection = DocumentCollection(
                department_id=department_id,
                collection_name=f"{department_name}_private",
                collection_type=DBDocumentPermissionLevel.PRIVATE.value,
                is_active=True,
                vector_config={
                    "embedding_model": "BAAI/bge-m3",
                    "vector_dim": 1024,
                    "index_type": "HNSW", 
                    "metric_type": "IP"
                }
            )
            
            self.db.add(public_collection)
            self.db.add(private_collection)
            await self.db.commit()
            
            collections_created = {
                "public": f"{department_name}_public",
                "private": f"{department_name}_private"
            }
            
            logger.info(f"Created collections for department {department_name}: {collections_created}")
            return collections_created
            
        except Exception as e:
            logger.error(f"Error creating department collections: {e}")
            await self.db.rollback()
            raise
    
    async def get_user_accessible_collections(
        self, 
        user_id: str
    ) -> List[Dict[str, Any]]:
        """
        Get all collections user can access across departments
        """
        try:
            user_query = select(User).options(
                joinedload(User.department)
            ).where(User.id == user_id)
            result = await self.db.execute(user_query)
            user = result.scalar_one_or_none()
            
            if not user:
                return []
            
            accessible_collections = []
            
            collections_query = select(DocumentCollection).options(
                joinedload(DocumentCollection.department)
            ).where(DocumentCollection.is_active == True)
            
            collections_result = await self.db.execute(collections_query)
            all_collections = collections_result.scalars().all()
            
            for collection in all_collections:
                if collection.collection_type == DBDocumentPermissionLevel.PUBLIC.value:
                    accessible_collections.append({
                        "collection_name": collection.collection_name,
                        "collection_type": collection.collection_type,
                        "department": collection.department.name,
                        "access_reason": "public_access"
                    })
                
                elif collection.collection_type == DBDocumentPermissionLevel.PRIVATE.value:
                    has_access = await self._check_private_collection_access(
                        user, collection
                    )
                    if has_access:
                        accessible_collections.append({
                            "collection_name": collection.collection_name,
                            "collection_type": collection.collection_type,
                            "department": collection.department.name,
                            "access_reason": "private_access_granted"
                        })
            
            return accessible_collections
            
        except Exception as e:
            logger.error(f"Error getting accessible collections: {e}")
            return []
    
    async def _check_private_collection_access(
        self, 
        user: User, 
        collection: DocumentCollection
    ) -> bool:
        """
        Check if user can access specific private collection
        """
        if user.role in [UserRole.MAINTAINER.value, UserRole.ADMIN.value]:
            return True
        
        if not user.department_id:
            return False
        
        if (str(user.department_id) == str(collection.department_id) and
            user.role in [
                UserRole.DEPT_ADMIN.value, 
                UserRole.DEPT_MANAGER.value,
                UserRole.USER.value 
            ]):
            return True
        
        return False
    
    async def validate_document_upload_permission(
        self, 
        user_id: str, 
        department_id: str, 
        access_level: str
    ) -> bool:
        """
        Validate if user can upload document with specified access level
        """
        try:
            user_query = select(User).where(User.id == user_id)
            result = await self.db.execute(user_query)
            user = result.scalar_one_or_none()
            
            if not user:
                return False
            
            if user.role in [UserRole.MAINTAINER.value, UserRole.ADMIN.value]:
                return True
            
            if access_level == AccessLevel.PRIVATE.value:
                if str(user.department_id) != str(department_id):
                    return False
                
                if user.role in [
                    UserRole.DEPT_ADMIN.value, 
                    UserRole.DEPT_MANAGER.value,
                    UserRole.USER.value
                ]:
                    return True
            
            elif access_level == AccessLevel.PUBLIC.value:
                if str(user.department_id) == str(department_id):
                    return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error validating upload permission: {e}")
            return False