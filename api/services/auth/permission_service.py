"""
Permission Service for RAG system with department-based access control
"""
from typing import List, Dict, Any, Optional, Set, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_
from sqlalchemy.orm import joinedload

from models.database.user import User
from models.database.document import Document, DocumentCollection
from models.database.tenant import Department
from common.types import AccessLevel, UserRole, DBDocumentPermissionLevel
from config.settings import get_settings
from utils.logging import get_logger
from core.exceptions import PermissionDeniedError, NotFoundError

logger = get_logger(__name__)
settings = get_settings()


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