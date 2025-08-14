import hashlib
import secrets
import string
from typing import Optional, List

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from fastapi import Request

from models.database.user import User
from models.database.auth import UserActionToken
from utils.password_utils import hash_password
from utils.email_utils import send_mail_async
from utils.logging import get_logger
from common.types import UserRole
from utils.request_utils import get_request_origin


logger = get_logger(__name__)


class InviteService:
    def __init__(self, db: AsyncSession):
        self.db = db

    @staticmethod
    def _gen_random_password(length: int = 12) -> str:
        alphabet = string.ascii_letters + string.digits + string.punctuation
        return ''.join(secrets.choice(alphabet) for _ in range(length))

    @staticmethod
    def _sanitize_username(name: str) -> str:
        safe = []
        for ch in name.lower():
            if ch.isalnum() or ch in ['.', '-', '_']:
                safe.append(ch)
        s = ''.join(safe).strip('._-')
        return s or f"user{secrets.randbelow(10**6):06d}"

    async def _generate_username_from_email(self, email: str, tenant_id: Optional[str]) -> str:
        local = email.split('@', 1)[0]
        base = self._sanitize_username(local)
        candidate = base
        suffix = 0
        while True:
            q = select(User).where(User.username == candidate)
            if tenant_id:
                q = q.where(User.tenant_id == tenant_id)
            result = await self.db.execute(q)
            exists = result.scalar_one_or_none()
            if not exists:
                return candidate
            suffix += 1
            candidate = f"{base}{suffix}"

    @staticmethod
    def _hash_token(token: str) -> str:
        return hashlib.sha256(token.encode('utf-8')).hexdigest()

    async def invite_admins(
        self,
        tenant_id: Optional[str],
        emails: List[str],
        request: Optional[Request] = None
    ) -> List[str]:
        invite_links: List[str] = []
        for email in emails:
            try:
                username = await self._generate_username_from_email(email, tenant_id)
                raw_password = self._gen_random_password()

                user = User(
                    username=username,
                    email=email,
                    hashed_password=hash_password(raw_password),
                    first_name="",
                    last_name="",
                    role=UserRole.ADMIN.value,
                    tenant_id=tenant_id,
                    is_active=True,
                    is_verified=False,
                )
                self.db.add(user)
                await self.db.flush()

                raw_token = secrets.token_urlsafe(32)
                token_hash = self._hash_token(raw_token)

                token = UserActionToken(
                    token_hash=token_hash,
                    token_type='invite',
                    email=email,
                    user_id=user.id,
                    tenant_id=tenant_id,
                    role=UserRole.ADMIN.value,
                    used=False,
                    expires_at=None
                )
                self.db.add(token)

                await self.db.commit()

                origin = get_request_origin(request) if request is not None else None
                invite_link = f"{origin}/invite#token={raw_token}" if origin else f"/invite#token={raw_token}"
                invite_links.append(invite_link)

                await send_mail_async(
                    template_name='invite.html.j2',
                    recipient_email=email,
                    subject="You're invited to AIChatBot",
                    context={
                        'action_url': invite_link,
                        'username': username,
                        'password': raw_password
                    },
                    rest_request=request
                )

                logger.info(f"Invited {email} to tenant {tenant_id}")
            except Exception as e:
                await self.db.rollback()
                logger.error(f"Failed to invite {email}: {e}")
        return invite_links

    async def accept_invite(self, raw_token: str, new_password: Optional[str] = None) -> bool:
        try:
            token_hash = self._hash_token(raw_token)
            result = await self.db.execute(
                select(UserActionToken).where(
                    UserActionToken.token_hash == token_hash,
                    UserActionToken.token_type == 'invite',
                    UserActionToken.used == False
                )
            )
            token = result.scalar_one_or_none()
            if not token:
                return False

            user_result = await self.db.execute(select(User).where(User.id == token.user_id))
            user = user_result.scalar_one_or_none()
            if not user:
                return False

            if new_password:
                user.hashed_password = hash_password(new_password)
            user.is_verified = True
            token.used = True

            await self.db.commit()
            return True
        except Exception as e:
            await self.db.rollback()
            logger.error(f"Accept invite failed: {e}")
            return False


