from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from models.document import DocumentFolder
from schema.response import FolderResponse
from schema.request import CreateFolderRequest
from datetime import datetime
import uuid


async def create_folder(
    session: AsyncSession,
    role: str,
    department_id: str,
    tenant_id: str,
    request: CreateFolderRequest,
) -> FolderResponse:
    if role == "USER":
        raise PermissionError("User dont have permisssion")

    # Kiểm tra parent folder nếu có
    parent_folder = None
    if request.parent_folder_id:
        parent_folder = await session.get(DocumentFolder, request.parent_folder_id)
        if not parent_folder:
            raise ValueError("Parent folder không tồn tại")

        # Nếu không phải ADMIN -> chỉ được tạo trong department của mình
        if role in ["DEPT_ADMIN", "DEPT_MANAGER"]:
            if parent_folder.department_id != department_id:
                raise PermissionError("Không được tạo folder trong department khác")

    # Nếu không có parent -> tạo root folder
    new_folder = DocumentFolder(
        id=uuid.uuid4(),
        department_id=department_id if role != "ADMIN" else (parent_folder.department_id if parent_folder else department_id),
        folder_name=request.folder_name,
        folder_path=(parent_folder.folder_path + "/" + request.folder_name) if parent_folder else "/" + request.folder_name,
        parent_folder_id=request.parent_folder_id,
        access_level="private",  # mặc định private, có thể chỉnh
        created_at=DateTimeManager.tenant_now_cached(tenant_id, self.db),
        updated_at=DateTimeManager.tenant_now_cached(tenant_id, self.db),
    )

    session.add(new_folder)
    await session.commit()
    await session.refresh(new_folder)

    return FolderResponse(
        id=new_folder.id,
        folder_name=new_folder.folder_name,
        folder_path=new_folder.folder_path,
        parent_folder_id=new_folder.parent_folder_id,
        created_at=new_folder.created_at,
        updated_at=new_folder.updated_at,
        documents=[],
        subfolders=[]
    )
