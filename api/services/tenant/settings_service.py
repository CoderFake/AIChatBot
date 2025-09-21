"""
Settings Service
Handles tenant settings management including logo, bot_name, region, language, etc.
"""
import uuid
from typing import Dict, Any, Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update

from models.database.tenant import Tenant
from services.cache.cache_manager import cache_manager
from utils.logging import get_logger

logger = get_logger(__name__)


class SettingsService:
    """
    Service for managing tenant settings
    """

    def __init__(self, db: AsyncSession):
        self.db = db
        self._cache_initialized = False

    async def _ensure_cache_initialized(self):
        """Ensure cache manager is initialized"""
        if not self._cache_initialized:
            self._cache_initialized = True

    async def get_tenant_settings(self, tenant_id: str) -> Dict[str, Any]:
        """
        Get tenant settings with caching
        """
        try:
            await self._ensure_cache_initialized()
            cache_key = f"tenant_config_{tenant_id}"

            cached_settings = await cache_manager.get(cache_key)
            if cached_settings:
                logger.info(f"Retrieved tenant settings from cache for tenant {tenant_id}")
                return cached_settings

            stmt = select(Tenant).where(Tenant.id == uuid.UUID(tenant_id))
            result = await self.db.execute(stmt)
            tenant = result.scalar_one_or_none()

            if not tenant:
                raise ValueError(f"Tenant {tenant_id} not found")

            default_settings = {
                "bot_name": "AI Assistant",
                "branding": {
                    "logo_url": None
                }
            }

            settings = default_settings.copy()
            if tenant.settings:
                self._deep_merge(settings, tenant.settings)

            await cache_manager.set(cache_key, settings, ttl=None)  
            logger.info(f"Cached tenant settings for tenant {tenant_id}")

            return settings

        except Exception as e:
            logger.error(f"Failed to get tenant settings for {tenant_id}: {e}")
            raise

    async def update_tenant_settings(self, tenant_id: str, settings_update: Dict[str, Any]) -> Dict[str, Any]:
        """
        Update tenant settings
        """
        try:
            current_settings = await self.get_tenant_settings(tenant_id)

            self._deep_merge(current_settings, settings_update)

            self._validate_settings(current_settings)

            stmt = (
                update(Tenant)
                .where(Tenant.id == uuid.UUID(tenant_id))
                .values(settings=current_settings)
            )
            await self.db.execute(stmt)
            await self.db.commit()

            await self._invalidate_settings_cache(tenant_id)

            logger.info(f"Updated tenant settings for tenant {tenant_id}")
            return current_settings

        except Exception as e:
            logger.error(f"Failed to update tenant settings for {tenant_id}: {e}")
            await self.db.rollback()
            raise

    async def update_specific_setting(self, tenant_id: str, key: str, value: Any) -> Dict[str, Any]:
        """
        Update a specific setting key
        """
        try:
            update_data = {key: value}
            return await self.update_tenant_settings(tenant_id, update_data)

        except Exception as e:
            logger.error(f"Failed to update specific setting {key} for tenant {tenant_id}: {e}")
            raise

    async def get_logo_url(self, tenant_id: str) -> Optional[str]:
        """
        Get logo URL from tenant settings
        """
        try:
            settings = await self.get_tenant_settings(tenant_id)
            return settings.get("branding", {}).get("logo_url")
        except Exception as e:
            logger.error(f"Failed to get logo URL for tenant {tenant_id}: {e}")
            return None

    async def get_bot_name(self, tenant_id: str) -> str:
        """
        Get bot name from tenant settings
        """
        try:
            settings = await self.get_tenant_settings(tenant_id)
            return settings.get("bot_name", "AI Assistant")
        except Exception as e:
            logger.error(f"Failed to get bot name for tenant {tenant_id}: {e}")
            return "AI Assistant"

    async def update_logo_url(self, tenant_id: str, logo_url: Optional[str]) -> Dict[str, Any]:
        """
        Update logo URL in tenant settings
        """
        try:
            update_data = {
                "branding": {
                    "logo_url": logo_url
                }
            }
            return await self.update_tenant_settings(tenant_id, update_data)
        except Exception as e:
            logger.error(f"Failed to update logo URL for tenant {tenant_id}: {e}")
            raise

    async def update_bot_name(self, tenant_id: str, bot_name: str) -> Dict[str, Any]:
        """
        Update bot name in tenant settings
        """
        try:
            if not bot_name or len(bot_name.strip()) == 0:
                raise ValueError("Bot name cannot be empty")
            if len(bot_name) > 100:
                raise ValueError("Bot name must be less than 100 characters")

            update_data = {
                "bot_name": bot_name.strip()
            }
            return await self.update_tenant_settings(tenant_id, update_data)
        except Exception as e:
            logger.error(f"Failed to update bot name for tenant {tenant_id}: {e}")
            raise

    def _deep_merge(self, base: Dict[str, Any], update: Dict[str, Any]) -> None:
        """
        Deep merge update dictionary into base dictionary
        """
        for key, value in update.items():
            if isinstance(value, dict) and key in base and isinstance(base[key], dict):
                self._deep_merge(base[key], value)
            else:
                base[key] = value

    def _validate_settings(self, settings: Dict[str, Any]) -> None:
        """
        Validate essential settings
        """
        if settings.get("branding", {}).get("logo_url"):
            logo_url = settings["branding"]["logo_url"]
            if not isinstance(logo_url, str):
                raise ValueError("logo_url must be a string")
            if not logo_url.startswith(("http://", "https://")):
                raise ValueError("logo_url must be a valid URL")

        if settings.get("bot_name"):
            if not isinstance(settings["bot_name"], str):
                raise ValueError("bot_name must be a string")
            if len(settings["bot_name"]) > 100:
                raise ValueError("bot_name must be less than 100 characters")

    async def _invalidate_settings_cache(self, tenant_id: str) -> None:
        """
        Invalidate settings cache for tenant.
        Also invalidates tenant details cache to maintain consistency.
        """
        try:
            await self._ensure_cache_initialized()

            cache_keys = [
                f"tenant_config_{tenant_id}",
                f"tenant:{tenant_id}:details"
            ]

            for cache_key in cache_keys:
                await cache_manager.delete(cache_key)
                logger.debug(f"Invalidated cache key: {cache_key}")

            logger.info(f"Invalidated all settings caches for tenant {tenant_id}")
        except Exception as e:
            logger.error(f"Failed to invalidate settings cache for tenant {tenant_id}: {e}")

    async def get_tenant_settings_with_mapping(self, tenant_id: str) -> Dict[str, Any]:
        """
        Get tenant settings with locale mapping for API responses
        """
        try:
            await self._ensure_cache_initialized()

            cache_key = f"tenant_config_{tenant_id}"
            cached_mapped_settings = await cache_manager.get(cache_key)
            if cached_mapped_settings:
                logger.info(f"Retrieved mapped tenant settings from cache for tenant {tenant_id}")
                return cached_mapped_settings

            stmt = select(Tenant).where(Tenant.id == uuid.UUID(tenant_id))
            result = await self.db.execute(stmt)
            tenant = result.scalar_one_or_none()

            if not tenant:
                raise ValueError(f"Tenant {tenant_id} not found")

            settings = await self.get_tenant_settings(tenant_id)

            locale_mapping = {
                "vi": "vi_VN",
                "en": "en_US",
                "ja": "ja_JP",
                "kr": "ko_KR",
                "zh": "zh_CN"
            }

            mapped_settings = {
                "tenant_name": tenant.tenant_name,
                "description": tenant.description,
                "timezone": tenant.timezone ,
                "locale": locale_mapping.get(tenant.locale, tenant.locale) if tenant.locale else "en_US",
                "chatbot_name": settings.get("bot_name", "AI Assistant"),
                "logo_url": settings.get("branding", {}).get("logo_url")
            }

            await cache_manager.set(cache_key, mapped_settings, ttl=None)
            logger.info(f"Cached mapped tenant settings for tenant {tenant_id}")

            return mapped_settings

        except Exception as e:
            logger.error(f"Failed to get tenant settings with mapping for {tenant_id}: {e}")
            raise

    async def update_tenant_basic_settings(
        self,
        tenant_id: str,
        tenant_name: Optional[str] = None,
        description: Optional[str] = None,
        timezone: Optional[str] = None,
        locale: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Update basic tenant settings (name, description, timezone, locale)
        """
        try:
            reverse_locale_mapping = {
                "vi_VN": "vi",
                "en_US": "en",
                "ja_JP": "ja",
                "ko_KR": "kr",
                "zh_CN": "zh",
                "zh_TW": "zh"
            }

            simple_locale = None
            if locale:
                simple_locale = reverse_locale_mapping.get(locale, locale.split('_')[0])

            stmt = select(Tenant).where(Tenant.id == uuid.UUID(tenant_id))
            result = await self.db.execute(stmt)
            tenant = result.scalar_one_or_none()

            if not tenant:
                raise ValueError(f"Tenant {tenant_id} not found")

            if tenant_name is not None:
                tenant.tenant_name = tenant_name
            if description is not None:
                tenant.description = description
            if timezone is not None:
                tenant.timezone = timezone
            if simple_locale is not None:
                tenant.locale = simple_locale

            await self.db.commit()
            await self.db.refresh(tenant)

            await self._invalidate_settings_cache(tenant_id)
            
            try:
                from services.tenant.tenant_service import TenantService
                tenant_service = TenantService(self.db)
                await tenant_service.invalidate_tenant_caches(tenant_id, ['agents'])
            except Exception as e:
                logger.warning(f"Could not invalidate tenant service caches: {e}")
            
            return await self.get_tenant_settings_with_mapping(tenant_id)

        except Exception as e:
            logger.error(f"Failed to update basic tenant settings for {tenant_id}: {e}")
            await self.db.rollback()
            raise

