import os
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from models.database.user import User
from utils.password_utils import hash_password
from utils.logging import get_logger
from common.types import UserRole
from common.types import Permission as PermissionEnum
from models.database.permission import Permission as PermissionModel
from services.auth.permission_service import PermissionService

logger = get_logger(__name__)


async def seed_global_maintainer(db: AsyncSession) -> Optional[str]:
    """
    Seed a global MAINTAINER account if not exists.
    Uses environment variables to avoid hard-code:
      MAINTAINER_USERNAME, MAINTAINER_EMAIL, MAINTAINER_PASSWORD
    Returns user_id if created or found.
    """
    username = os.getenv("MAINTAINER_USERNAME")
    email = os.getenv("MAINTAINER_EMAIL")
    password = os.getenv("MAINTAINER_PASSWORD")

    if not (username and email and password):
        logger.info("Maintainer seed skipped: missing MAINTAINER_* envs")
        return None

    result = await db.execute(select(User).where(User.username == username))
    user = result.scalar_one_or_none()

    if user:
        logger.info("Maintainer already exists; skipping creation")
        return str(user.id)

    user = User(
        username=username,
        email=email,
        hashed_password=hash_password(password),
        first_name="System",
        last_name="Maintainer",
        role=UserRole.MAINTAINER.value,
        is_active=True,
        is_verified=True,
    )
    db.add(user)
    await db.flush()
    await db.commit()

    logger.info(f"Maintainer account created: {username}")
    return str(user.id) 


async def seed_permissions(db: AsyncSession) -> None:
    """Seed fixed permission catalog based on common.types.Permission enum."""
    try:
        service = PermissionService(db)
        existing = await db.execute(select(PermissionModel.permission_code))
        existing_codes = {row[0] for row in existing.all()}

        created = 0
        for perm in PermissionEnum:
            code = perm.value
            if code in existing_codes:
                continue
                
            parts = code.split('.')
            resource_type = parts[0] if parts else code
            action = parts[-1] if parts else code
            name = code.replace('.', ' ').title()
            await service.create_permission(
                permission_code=code,
                permission_name=name,
                resource_type=resource_type,
                action=action,
                is_system=True,
                created_by=None
            )
            created += 1
        if created:
            logger.info(f"Seeded {created} permissions into catalog")
        else:
            logger.info("Permissions already seeded; no changes")
    except Exception as e:
        logger.error(f"Failed to seed permissions: {e}")