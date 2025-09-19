import hashlib
import secrets
import string
from typing import Optional, List, Dict, Any

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from fastapi import Request

from models.database.user import User
from models.database.auth import UserActionToken
from models.database.tenant import Department
from utils.password_utils import hash_password
from utils.email_utils import send_mail_async
from utils.logging import get_logger
from common.types import UserRole
from utils.request_utils import get_request_origin
from datetime import datetime, timedelta
from utils.datetime_utils import DateTimeManager
from config.settings import get_settings


logger = get_logger(__name__)


class InviteService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.settings = get_settings()

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

    async def _generate_invite_link(self, tenant_id: Optional[str], raw_token: str, request: Optional[Request] = None) -> str:
        """Generate invite link based on tenant configuration"""
        try:
            base_url = None
            if tenant_id:
                from models.database.tenant import Tenant
                tenant_result = await self.db.execute(
                    select(Tenant).where(Tenant.id == tenant_id)
                )
                tenant = tenant_result.scalar_one_or_none()
                if tenant and tenant.sub_domain:
                    origin = get_request_origin(request) if request else None
                    if origin:
                        from urllib.parse import urlparse
                        parsed = urlparse(origin)
                        domain = parsed.netloc.split(':')[0]

                        domain_parts = domain.split('.')
                        if len(domain_parts) >= 3:
                            base_domain = '.'.join(domain_parts[1:])
                            base_url = f"{parsed.scheme}://{tenant.sub_domain}.{base_domain}"
                        elif len(domain_parts) == 2:
                            base_url = f"{parsed.scheme}://{tenant.sub_domain}.{domain}"
                        else:
                            base_url = f"{parsed.scheme}://{tenant.sub_domain}.{domain}"
                    else:
                        base_url = f"https://{tenant.sub_domain}.localhost:3000"
                elif tenant:
                    origin = get_request_origin(request) if request else None
                    if origin:
                        base_url = origin
                    else:
                        base_url = "http://localhost:3000"

            if not base_url:
                origin = get_request_origin(request) if request else None
                base_url = origin or "http://localhost:3000"

            if tenant and tenant.sub_domain:
                invite_url = f"{base_url}/invite#token={raw_token}"
            else:
                invite_url = f"{base_url}/{tenant_id}/invite#token={raw_token}"
            logger.info(f"Generated invite link for tenant {tenant_id}: {invite_url}")
            return invite_url

        except Exception as e:
            logger.error(f"Failed to generate invite link for tenant {tenant_id}: {e}")
            origin = get_request_origin(request) if request else None
            base_url = origin or "http://localhost:3000"

            if tenant and tenant.sub_domain:
                fallback_url = f"{base_url}/invite#token={raw_token}"
            else:
                fallback_url = f"{base_url}/{tenant_id}/invite#token={raw_token}"
            logger.info(f"Using fallback invite link: {fallback_url}")
            return fallback_url

    async def invite_admins(
        self,
        tenant_id: Optional[str],
        emails: List[str],
        request: Optional[Request] = None
    ) -> List[str]:
        invite_links: List[str] = []
        for email in emails:
            try:
                existing_user = await self._check_existing_user(email, tenant_id)
                if existing_user:
                    invite_link = await self._invite_existing_user(
                        existing_user, UserRole.ADMIN, None, request, None
                    )
                else:
                    invite_link = await self._invite_new_user(
                        email, UserRole.ADMIN, tenant_id, None, request, None
                    )
                invite_links.append(invite_link)
            except Exception as e:
                logger.error(f"Failed to invite admin {email}: {e}")
        return invite_links

    async def _check_existing_user(self, email: str, tenant_id: Optional[str] = None) -> Optional[User]:
        """Check if user already exists in the system"""
        query = select(User).where(User.email == email, User.is_deleted == False)
        if tenant_id:
            query = query.where(User.tenant_id == tenant_id)
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def _invite_new_user(
        self,
        email: str,
        role: UserRole,
        tenant_id: Optional[str],
        department_id: Optional[str],
        request: Optional[Request] = None,
        invited_by: Optional[str] = None
    ) -> str:
        """Invite a completely new user to the system"""
        username = await self._generate_username_from_email(email, tenant_id)
        raw_password = self._gen_random_password()

        user = User(
            username=username,
            email=email,
            hashed_password=hash_password(raw_password),
            first_name="",
            last_name="",
            role=role.value,
            tenant_id=tenant_id,
            department_id=department_id,
            is_active=True,
            is_verified=False,
        )
        self.db.add(user)
        await self.db.flush()

        raw_token = secrets.token_urlsafe(32)
        token_hash = self._hash_token(raw_token)

        token = UserActionToken(
            token_hash=token_hash,
            token_type='invite_new_user',
            email=email,
            user_id=user.id,
            tenant_id=tenant_id,
            role=role.value,
            used=False,
            expires_at=DateTimeManager._now() + timedelta(days=self.settings.INVITE_TOKEN_TTL_DAYS)
        )
        self.db.add(token)

        await self.db.commit()

        invite_link = await self._generate_invite_link(tenant_id, raw_token, request)

        template_name = self._get_invite_template_name(role)
        subject = self._get_invite_subject(role)

        try:
            await send_mail_async(
                template_name=template_name,
                recipient_email=email,
                subject=subject,
                context={
                    'action_url': invite_link,
                    'username': username,
                    'password': raw_password,
                    'role': role.value,
                    'tenant_id': tenant_id,
                    'department_id': department_id
                },
                rest_request=request
            )
        except Exception as mail_error:
            logger.warning(f"Failed to send invite email to {email}: {mail_error}")

        logger.info(f"Invited new user {email} as {role.value} to tenant {tenant_id}, dept {department_id}")
        return invite_link

    async def _invite_existing_user(
        self,
        user: User,
        new_role: UserRole,
        department_id: Optional[str],
        request: Optional[Request] = None,
        invited_by: Optional[str] = None
    ) -> str:
        """Invite existing user to new role/department"""
        try:
            raw_token = secrets.token_urlsafe(32)
            token_hash = self._hash_token(raw_token)

            token = UserActionToken(
                token_hash=token_hash,
                token_type='invite_existing_user',
                email=user.email,
                user_id=user.id,
                tenant_id=user.tenant_id,
                role=new_role.value,
                used=False,
                expires_at=DateTimeManager._now() + timedelta(days=self.settings.INVITE_TOKEN_TTL_DAYS)
            )
            self.db.add(token)
            await self.db.commit()
            logger.info(f"Created invite_existing_user token for user {user.email} with hash {token_hash}")

            invite_link = await self._generate_invite_link(user.tenant_id, raw_token, request)

            try:
                await send_mail_async(
                    template_name='invite_existing.html.j2',
                    recipient_email=user.email,
                    subject=f"You're invited to join as {new_role.value}",
                    context={
                        'action_url': invite_link,
                        'username': user.username,
                        'role': new_role.value,
                        'department_id': department_id
                    },
                    rest_request=request
                )
            except Exception as mail_error:
                logger.warning(f"Failed to send invite email to {user.email}: {mail_error}")
                # Don't fail the invite if email sending fails - token is still valid

            logger.info(f"Invited existing user {user.email} to new role {new_role.value}")
            return invite_link
        except Exception as e:
            logger.error(f"Failed to invite existing user {user.email}: {e}")
            raise

    def _get_invite_template_name(self, role: UserRole) -> str:
        """Get appropriate email template based on role"""
        templates = {
            UserRole.ADMIN: 'invite_admin.html.j2',
            UserRole.DEPT_ADMIN: 'invite_dept_admin.html.j2',
            UserRole.DEPT_MANAGER: 'invite_dept_manager.html.j2',
            UserRole.USER: 'invite_user.html.j2',
        }
        return templates.get(role, 'invite.html.j2')

    def _get_invite_subject(self, role: UserRole) -> str:
        """Get appropriate email subject based on role"""
        subjects = {
            UserRole.ADMIN: "You're invited to join as Administrator",
            UserRole.DEPT_ADMIN: "You're invited to join as Department Administrator",
            UserRole.DEPT_MANAGER: "You're invited to join as Department Manager",
            UserRole.USER: "You're invited to join as User",
        }
        return subjects.get(role, "You're invited to AIChatBot")

    async def invite_department_admins(
        self,
        tenant_id: str,
        department_id: str,
        emails: List[str],
        request: Optional[Request] = None,
        invited_by: Optional[str] = None
    ) -> List[str]:
        """Admin invites department admins to department"""
        invite_links = []
        for email in emails:
            try:
                existing_user = await self._check_existing_user(email, tenant_id)
                if existing_user:
                    invite_link = await self._invite_existing_user(
                        existing_user, UserRole.DEPT_ADMIN, department_id, request, invited_by
                    )
                else:
                    invite_link = await self._invite_new_user(
                        email, UserRole.DEPT_ADMIN, tenant_id, department_id, request, invited_by
                    )
                invite_links.append(invite_link)
            except Exception as e:
                logger.error(f"Failed to invite department admin {email}: {e}")
        return invite_links

    async def invite_department_managers(
        self,
        tenant_id: str,
        department_id: str,
        emails: List[str],
        request: Optional[Request] = None,
        invited_by: Optional[str] = None
    ) -> List[str]:
        """Admin/Dept Admin invites department managers"""
        invite_links = []
        for email in emails:
            try:
                existing_user = await self._check_existing_user(email, tenant_id)
                if existing_user:
                    invite_link = await self._invite_existing_user(
                        existing_user, UserRole.DEPT_MANAGER, department_id, request, invited_by
                    )
                else:
                    invite_link = await self._invite_new_user(
                        email, UserRole.DEPT_MANAGER, tenant_id, department_id, request, invited_by
                    )
                invite_links.append(invite_link)
            except Exception as e:
                logger.error(f"Failed to invite department manager {email}: {e}")
        return invite_links

    async def invite_users(
        self,
        tenant_id: str,
        department_id: str,
        emails: List[str],
        request: Optional[Request] = None,
        invited_by: Optional[str] = None
    ) -> List[str]:
        """Admin/Dept Admin/Dept Manager invites users"""
        invite_links = []
        for email in emails:
            try:
                existing_user = await self._check_existing_user(email, tenant_id)
                if existing_user:
                    invite_link = await self._invite_existing_user(
                        existing_user, UserRole.USER, department_id, request, invited_by
                    )
                else:
                    invite_link = await self._invite_new_user(
                        email, UserRole.USER, tenant_id, department_id, request, invited_by
                    )
                invite_links.append(invite_link)
            except Exception as e:
                logger.error(f"Failed to invite user {email}: {e}")
        return invite_links

    async def validate_invite_token(self, raw_token: str) -> Optional[Dict[str, Any]]:
        """
        Validate invite token and return user info without accepting
        Returns dict with user info or None if invalid
        """
        try:
            token_hash = self._hash_token(raw_token)
            result = await self.db.execute(
                select(UserActionToken).where(
                    UserActionToken.token_hash == token_hash,
                    UserActionToken.token_type.in_(['invite', 'invite_new_user', 'invite_existing_user']),
                    UserActionToken.used == False
                )
            )
            token_record = result.scalar_one_or_none()
            if not token_record:
                logger.warning(f"Token not found for hash {token_hash}")
                return None

            if token_record.expires_at and token_record.expires_at <= DateTimeManager._now():
                logger.info(f"Invite token expired for user {token_record.user_id}")
                return None

            user_result = await self.db.execute(select(User).where(User.id == token_record.user_id))
            user = user_result.scalar_one_or_none()
            if not user:
                return None

            tenant_name = "Organization"
            if user.tenant_id:
                from models.database.tenant import Tenant
                tenant_result = await self.db.execute(
                    select(Tenant.tenant_name).where(Tenant.id == user.tenant_id)
                )
                tenant_data = tenant_result.scalar_one_or_none()
                if tenant_data:
                    tenant_name = tenant_data

            return {
                "email": user.email,
                "username": user.username,
                "role": token_record.role,
                "tenant_id": user.tenant_id,
                "tenant_name": tenant_name,
                "token_type": token_record.token_type
            }

        except Exception as e:
            logger.error(f"Validate invite token failed: {e}")
            return None

    async def accept_invite(self, raw_token: str, new_password: str) -> bool:
        """
        Accept invitation - requires password change for first login
        """
        try:
            if not new_password:
                logger.error("Password required for invite acceptance")
                return False

            token_hash = self._hash_token(raw_token)
            result = await self.db.execute(
                select(UserActionToken).where(
                    UserActionToken.token_hash == token_hash,
                    UserActionToken.token_type.in_(['invite', 'invite_new_user', 'invite_existing_user']),
                    UserActionToken.used == False
                )
            )
            token = result.scalar_one_or_none()
            if not token:
                return False

            if token.expires_at and token.expires_at <= DateTimeManager._now():
                logger.info(f"Invite token expired for user {token.user_id}")
                return False

            user_result = await self.db.execute(select(User).where(User.id == token.user_id))
            user = user_result.scalar_one_or_none()
            if not user:
                return False

            user.hashed_password = hash_password(new_password)
            user.is_verified = True

            user.last_login = DateTimeManager._now()

            if token.token_type == 'invite_new_user':
                user.last_login = None
            elif token.token_type == 'invite_existing_user':
                user.role = token.role
                user.is_active = True

            token.used = True

            await self.db.commit()
            logger.info(f"User {user.email} accepted invite with password change, role: {user.role}, dept: {user.department_id}, active: {user.is_active}, verified: {user.is_verified}")
            return True
        except Exception as e:
            await self.db.rollback()
            logger.error(f"Accept invite failed: {e}")
            return False


