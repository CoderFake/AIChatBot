import hashlib
import secrets
from datetime import timedelta
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_

from models.database.user import User
from models.database.auth import UserActionToken
from utils.password_utils import hash_password
from utils.datetime_utils import DateTimeManager
from utils.email_utils import send_mail_async
from utils.logging import get_logger
from config.settings import get_settings
from utils.request_utils import get_request_origin


logger = get_logger(__name__)
settings = get_settings()


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode('utf-8')).hexdigest()


class ResetService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_reset_token(self, user: User) -> Optional[str]:
        try:
            raw_token = secrets.token_urlsafe(32)
            token_hash = _hash_token(raw_token)
            token = UserActionToken(
                token_hash=token_hash,
                token_type='reset',
                user_id=user.id,
                used=False,
                expires_at=DateTimeManager._now() + timedelta(minutes=settings.RESET_TOKEN_TTL_MINUTES)
            )
            self.db.add(token)
            await self.db.commit()
            return raw_token
        except Exception as e:
            await self.db.rollback()
            logger.error(f"Create reset token failed: {e}")
            return None

    async def request_password_reset(self, username_or_email: str, request=None, tenant_id: Optional[str] = None) -> bool:
        """Request password reset for user by username or email"""
        try:
            query = select(User).where(
                or_(User.username == username_or_email, User.email == username_or_email),
                User.is_active == True,
                User.is_deleted == False
            )
            if tenant_id:
                query = query.where(User.tenant_id == tenant_id)

            result = await self.db.execute(query)
            user = result.scalar_one_or_none()

            if not user:
                return True

            return await self.send_reset_email(user, request)
        except Exception as e:
            logger.error(f"Request password reset failed: {e}")
            return False

    async def send_reset_email(self, user: User, request) -> bool:
        raw_token = await self.create_reset_token(user)
        if not raw_token:
            return False

        origin = get_request_origin(request) if request is not None else None
        tenant_prefix = f"/{user.tenant_id}" if user.tenant_id else ""
        reset_link = f"{origin}{tenant_prefix}/reset-password#token={raw_token}" if origin else f"{tenant_prefix}/reset-password#token={raw_token}"

        try:
            await send_mail_async(
                template_name='reset.html.j2',
                recipient_email=user.email,
                subject='Reset your password',
                context={'action_url': reset_link, 'username': user.username},
                rest_request=request
            )
            return True
        except Exception as e:
            logger.error(f"Send reset email failed: {e}")
            return False

    async def reset_password(self, raw_token: str, new_password: str) -> bool:
        try:
            token_hash = _hash_token(raw_token)
            result = await self.db.execute(
                select(UserActionToken).where(
                    UserActionToken.token_hash == token_hash,
                    UserActionToken.token_type == 'reset',
                    UserActionToken.used == False
                )
            )
            token = result.scalar_one_or_none()
            if not token or (token.expires_at and token.expires_at <= DateTimeManager._now()):
                return False

            user_result = await self.db.execute(select(User).where(User.id == token.user_id))
            user = user_result.scalar_one_or_none()
            if not user:
                return False

            user.hashed_password = hash_password(new_password)
            token.used = True
            await self.db.commit()
            return True
        except Exception as e:
            await self.db.rollback()
            logger.error(f"Reset password failed: {e}")
            return False


