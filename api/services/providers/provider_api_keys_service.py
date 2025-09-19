"""
Provider API Keys Service
Handles API key management for tenant providers
"""
import uuid
from typing import Dict, Any, Optional, List

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from sqlalchemy.orm import selectinload

from models.database.provider import Provider, ProviderModel, TenantProviderConfig
from services.cache.cache_manager import cache_manager
from utils.logging import get_logger

logger = get_logger(__name__)


class ProviderApiKeysService:
    """
    Service for managing provider API keys
    """

    def __init__(self, db: AsyncSession):
        self.db = db
        self._cache_initialized = False

    async def _ensure_cache_initialized(self):
        """Ensure cache manager is initialized"""
        if not self._cache_initialized:
            self._cache_initialized = True

    async def get_provider_api_keys(self, tenant_id: str, provider_name: str) -> Dict[str, Any]:
        """
        Get API keys for a specific provider
        """
        try:
            await self._ensure_cache_initialized()
            cache_key = f"provider_api_keys_{tenant_id}_{provider_name}"

            cached_keys = await cache_manager.get(cache_key)
            if cached_keys:
                return cached_keys

            result = await self.db.execute(
                select(TenantProviderConfig)
                .join(Provider, Provider.id == TenantProviderConfig.provider_id)
                .where(
                    and_(
                        TenantProviderConfig.tenant_id == uuid.UUID(tenant_id),
                        Provider.provider_name == provider_name,
                        TenantProviderConfig.is_enabled == True
                    )
                )
            )
            config = result.scalar_one_or_none()

            if not config:
                result_data = {
                    "provider_name": provider_name,
                    "api_keys": [],
                    "total_keys": 0
                }
            else:
                api_keys = config.api_keys or []
                result_data = {
                    "provider_name": provider_name,
                    "api_keys": api_keys,
                    "total_keys": len(api_keys)
                }

            await cache_manager.set(cache_key, result_data, ttl=None)  
            return result_data

        except Exception as e:
            logger.error(f"Failed to get API keys for provider {provider_name}: {e}")
            return {
                "provider_name": provider_name,
                "api_keys": [],
                "total_keys": 0
            }

    async def update_provider_api_keys(
        self,
        tenant_id: str,
        provider_name: str,
        api_keys: List[str]
    ) -> Dict[str, Any]:
        """
        Update API keys for a provider
        """
        try:
            # Validate API keys
            if not api_keys or len(api_keys) == 0:
                raise ValueError("At least one API key is required")

            if any(not key.strip() for key in api_keys):
                raise ValueError("API keys cannot be empty")

            result = await self.db.execute(
                select(TenantProviderConfig)
                .join(Provider, Provider.id == TenantProviderConfig.provider_id)
                .where(
                    and_(
                        TenantProviderConfig.tenant_id == uuid.UUID(tenant_id),
                        Provider.provider_name == provider_name
                    )
                )
            )
            config = result.scalar_one_or_none()

            if not config:
                provider_result = await self.db.execute(
                    select(Provider).where(Provider.provider_name == provider_name)
                )
                provider = provider_result.scalar_one_or_none()

                if not provider:
                    raise ValueError(f"Provider {provider_name} not found")

                # Create new config
                config = TenantProviderConfig(
                    tenant_id=uuid.UUID(tenant_id),
                    provider_id=provider.id,
                    is_enabled=True
                )
                self.db.add(config)

            config.set_api_keys(api_keys)
            await self.db.commit()
            await self.db.refresh(config)

            await self._invalidate_provider_cache(tenant_id, provider_name)

            updated_api_keys = config.api_keys or []
            return {
                "provider_name": provider_name,
                "api_keys": updated_api_keys,
                "total_keys": len(updated_api_keys)
            }

        except Exception as e:
            logger.error(f"Failed to update API keys for provider {provider_name}: {e}")
            await self.db.rollback()
            raise

    async def _invalidate_provider_cache(self, tenant_id: str, provider_name: str) -> None:
        """
        Invalidate provider API keys cache
        """
        try:
            await self._ensure_cache_initialized()

            cache_keys = [
                f"provider_api_keys_{tenant_id}_{provider_name}"
                f"tenant_provider_config:{tenant_id}:{provider_name}"
            ]

            for cache_key in cache_keys:
                try:
                    await cache_manager.delete(cache_key)
                    logger.debug(f"Invalidated cache key: {cache_key}")
                except Exception as e:
                    logger.debug(f"Could not delete cache key {cache_key}: {e}")

            logger.info(f"Invalidated all provider caches for {tenant_id}/{provider_name}")
        except Exception as e:
            logger.error(f"Failed to invalidate provider cache for {tenant_id}/{provider_name}: {e}")

    async def validate_api_keys_format(self, api_keys: List[str]) -> bool:
        """
        Validate API keys format and requirements
        """
        try:
            if not api_keys or len(api_keys) == 0:
                return False

            if any(not key.strip() for key in api_keys):
                return False

            if any(len(key.strip()) < 10 for key in api_keys):
                return False

            return True

        except Exception as e:
            logger.error(f"Failed to validate API keys format: {e}")
            return False
