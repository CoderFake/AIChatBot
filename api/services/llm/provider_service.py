from typing import Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from models.database.provider import Provider, ProviderModel
from services.llm.provider_registry import provider_registry
from utils.logging import get_logger

logger = get_logger(__name__)


class ProviderService:
    """Service to sync default provider registry with the database"""

    def __init__(self, db_session: AsyncSession):
        self.db = db_session

    async def initialize(self) -> None:
        """Sync providers and models from registry to database"""
        await self._sync_registry_to_database()

    async def _sync_registry_to_database(self) -> None:
        """Insert or update provider and model definitions"""
        try:
            registry_providers = provider_registry.get_all_providers()

            result = await self.db.execute(select(Provider))
            existing = {p.provider_name: p for p in result.scalars().all()}

            providers_added = 0
            providers_updated = 0

            for name, info in registry_providers.items():
                base_config = info.get("provider_config", {})
                provider = existing.get(name)

                if provider is None:
                    provider = Provider(
                        provider_name=name,
                        base_config=base_config,
                        is_enabled=False,
                    )
                    self.db.add(provider)
                    await self.db.flush()
                    existing[name] = provider
                    providers_added += 1
                    logger.info(f"Added new provider to database: {name}")
                else:
                    provider.base_config = base_config
                    providers_updated += 1
                    logger.debug(f"Updated provider metadata: {name}")

                await self._sync_provider_models(provider.id, info)

            if providers_added > 0 or providers_updated > 0:
                await self.db.commit()
                logger.info(
                    f"Provider registry sync completed - Added: {providers_added}, Updated: {providers_updated}"
                )
        except Exception as exc:
            await self.db.rollback()
            logger.error(f"Failed to sync provider registry to database: {exc}")
            raise

    async def _sync_provider_models(self, provider_id, info: Dict[str, Any]) -> None:
        """Ensure provider models exist in database"""
        result = await self.db.execute(
            select(ProviderModel).where(ProviderModel.provider_id == provider_id)
        )
        existing_models = {m.model_name: m for m in result.scalars().all()}

        for model_name in info.get("models", []):
            if model_name not in existing_models:
                model = ProviderModel(
                    provider_id=provider_id,
                    model_name=model_name,
                    model_type="chat",
                    is_enabled=False,
                )
                self.db.add(model)
            else:
                existing_models[model_name].model_type = "chat"

        await self.db.flush()
