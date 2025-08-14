import os
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from models.database.user import User
from utils.password_utils import hash_password
from utils.logging import get_logger
from common.types import UserRole

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