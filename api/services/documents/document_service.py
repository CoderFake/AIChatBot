from typing import Optional, Dict
from sqlalchemy.orm import Session
from sqlalchemy import and_
from utils.logging import get_logger
import asyncio

from models.database.tenant import Department
from models.database.document import DocumentFolder, DocumentCollection
from services.vector.milvus_service import milvus_service
from common.types import DBDocumentPermissionLevel

logger = get_logger(__name__)


class DocumentService:
    """
    Document service for creating department root folder and Milvus collections.
    - Root folder: one per department with folder_path "/"
    - Collections: {tenant_id}-{department_id}-public/private
    """

    def __init__(self, db_session: Session):
        self.db = db_session

    def _ensure_milvus_collections(self, public_name: str, private_name: str) -> None:
        """Best-effort ensure Milvus collections exist using milvus_service (async)."""
        async def _runner():
            await asyncio.gather(
                milvus_service.ensure_collection_exists(
                    collection_name=public_name,
                    milvus_instance=DBDocumentPermissionLevel.PUBLIC.value,
                ),
                milvus_service.ensure_collection_exists(
                    collection_name=private_name,
                    milvus_instance=DBDocumentPermissionLevel.PRIVATE.value,
                ),
            )
        try:
            try:
                loop = asyncio.get_running_loop()
                loop.create_task(_runner())
            except RuntimeError:
                asyncio.run(_runner())
        except Exception as e:
            logger.warning(f"Milvus ensure collections failed: {e}")

    def create_department_root(self, tenant_id: str, department_id: str) -> Optional[Dict[str, str]]:
        """
        Create root folder and two collections (public/private) for a department.
        Returns dict with document_root_id and collection names if success.
        """
        try:
            department: Optional[Department] = (
                self.db.query(Department).filter(Department.id == department_id).first()
            )
            if not department:
                logger.error(f"Department {department_id} not found for document root")
                return None

            existing_root: Optional[DocumentFolder] = (
                self.db.query(DocumentFolder)
                .filter(
                    and_(
                        DocumentFolder.department_id == department_id,
                        DocumentFolder.folder_path == "/",
                    )
                )
                .first()
            )
            if existing_root:
                root_folder = existing_root
            else:
                root_folder = DocumentFolder(
                    department_id=department_id,
                    folder_name="root",
                    folder_path="/",
                    access_level="public",
                )
                self.db.add(root_folder)
                self.db.flush()

            public_name = f"{tenant_id}-{department_id}-public"
            private_name = f"{tenant_id}-{department_id}-private"

            existing_public = (
                self.db.query(DocumentCollection)
                .filter(
                    and_(
                        DocumentCollection.department_id == department_id,
                        DocumentCollection.collection_type == "public_milvus",
                    )
                )
                .first()
            )
            if not existing_public:
                public_collection = DocumentCollection(
                    department_id=department_id,
                    collection_name=public_name,
                    collection_type="public_milvus",
                    is_active=True,
                )
                self.db.add(public_collection)
            else:
                public_name = existing_public.collection_name

            existing_private = (
                self.db.query(DocumentCollection)
                .filter(
                    and_(
                        DocumentCollection.department_id == department_id,
                        DocumentCollection.collection_type == "private_milvus",
                    )
                )
                .first()
            )
            if not existing_private:
                private_collection = DocumentCollection(
                    department_id=department_id,
                    collection_name=private_name,
                    collection_type="private_milvus",
                    is_active=True,
                )
                self.db.add(private_collection)
            else:
                private_name = existing_private.collection_name

            self._ensure_milvus_collections(public_name, private_name)

            return {
                "document_root_id": str(root_folder.id),
                "public_collection": public_name,
                "private_collection": private_name,
            }
        except Exception as e:
            logger.error(f"Failed to create department root for {department_id}: {e}")
            return None 