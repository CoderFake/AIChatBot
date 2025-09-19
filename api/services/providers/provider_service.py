"""
Provider Service
Manages provider configurations and API key encryption with async operations
"""
from typing import Dict, List, Optional, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from sqlalchemy.exc import SQLAlchemyError
from models.database.provider import Provider, ProviderModel, TenantProviderConfig
from utils.logging import get_logger
from utils.encryption_utils import encryption_service

logger = get_logger(__name__)


class ProviderService:
    """
    Service for provider configuration management with async operations
    Each method handles its own errors and raises exceptions for transaction rollback
    """
    
    def __init__(self, db_session: AsyncSession):
        self.db = db_session
    
    async def get_provider_by_id(self, provider_id: str) -> Optional[Dict[str, Any]]:
        """
        Get provider by ID
        """
        try:
            result = await self.db.execute(
                select(Provider).where(Provider.id == provider_id)
            )
            provider = result.scalar_one_or_none()
            
            if not provider:
                logger.warning(f"Provider {provider_id} not found")
                return None
            
            return {
                "id": str(provider.id),
                "provider_name": provider.provider_name,
                "is_enabled": provider.is_enabled,
                "base_config": provider.base_config or {}
            }
            
        except SQLAlchemyError as e:
            logger.error(f"Database error getting provider {provider_id}: {e}")
            raise RuntimeError(f"Database error getting provider: {e}")
        except Exception as e:
            logger.error(f"Failed to get provider {provider_id}: {e}")
            raise RuntimeError(f"Failed to get provider: {e}")
    
    async def get_model_by_id(self, model_id: str) -> Optional[Dict[str, Any]]:
        """
        Get model by ID
        """
        try:
            result = await self.db.execute(
                select(ProviderModel).where(ProviderModel.id == model_id)
            )
            model = result.scalar_one_or_none()
            
            if not model:
                logger.warning(f"Model {model_id} not found")
                return None
            
            return {
                "id": str(model.id),
                "model_name": model.model_name,
                "model_type": model.model_type,
                "provider_id": str(model.provider_id),
                "is_enabled": model.is_enabled,
                "model_config": model.model_config or {}
            }
            
        except SQLAlchemyError as e:
            logger.error(f"Database error getting model {model_id}: {e}")
            raise RuntimeError(f"Database error getting model: {e}")
        except Exception as e:
            logger.error(f"Failed to get model {model_id}: {e}")
            raise RuntimeError(f"Failed to get model: {e}")
    
    async def validate_provider_and_model(self, provider_id: str, model_id: Optional[str] = None) -> bool:
        """
        Validate provider exists and model belongs to provider (if provided)
        """
        try:
            result = await self.db.execute(
                select(Provider).where(
                    and_(
                        Provider.id == provider_id,
                        Provider.is_enabled == True
                    )
                )
            )
            provider = result.scalar_one_or_none()
            
            if not provider:
                logger.error(f"Provider {provider_id} not found or disabled")
                raise ValueError(f"Provider {provider_id} not found or disabled")
            
            if model_id:
                model_result = await self.db.execute(
                    select(ProviderModel).where(
                        and_(
                            ProviderModel.id == model_id,
                            ProviderModel.provider_id == provider_id,
                            ProviderModel.is_enabled == True
                        )
                    )
                )
                model = model_result.scalar_one_or_none()
                
                if not model:
                    logger.error(f"Model {model_id} not found or not belongs to provider {provider_id}")
                    raise ValueError(f"Model {model_id} not found or not belongs to provider")
            
            return True
            
        except ValueError:
            raise
        except SQLAlchemyError as e:
            logger.error(f"Database error validating provider/model: {e}")
            raise RuntimeError(f"Database error validating provider/model: {e}")
        except Exception as e:
            logger.error(f"Failed to validate provider/model: {e}")
            raise RuntimeError(f"Failed to validate provider/model: {e}")
    
    async def create_or_update_tenant_provider_config(
        self,
        tenant_id: str,
        provider_id: str,
        api_keys: List[str],
        config_data: Optional[Dict[str, Any]] = None,
        rotation_strategy: str = "round_robin"
    ) -> Dict[str, Any]:
        """
        Create or update tenant provider configuration with encrypted API keys
        Raises exception on error for transaction rollback
        """
        try:
            if not api_keys:
                logger.error("API keys cannot be empty")
                raise ValueError("API keys cannot be empty")
        
            await self.validate_provider_and_model(provider_id)
            
            result = await self.db.execute(
                select(TenantProviderConfig).where(
                    and_(
                        TenantProviderConfig.tenant_id == tenant_id,
                        TenantProviderConfig.provider_id == provider_id
                    )
                )
            )
            existing_config = result.scalar_one_or_none()
            
            if existing_config:
                existing_config.set_api_keys(api_keys)  
                existing_config.current_key_index = 0 
                existing_config.rotation_strategy = rotation_strategy
                existing_config.is_enabled = True
                
                if config_data:
                    existing_config.config_data = config_data

                await self.db.flush()

                result = {
                    "id": str(existing_config.id),
                    "tenant_id": tenant_id,
                    "provider_id": provider_id,
                    "key_count": len(api_keys),
                    "rotation_strategy": rotation_strategy,
                    "is_enabled": True,
                    "action": "updated"
                }
                
                logger.info(f"Updated tenant provider config for tenant {tenant_id}, provider {provider_id}")
                
            else:
                new_config = TenantProviderConfig(
                    tenant_id=tenant_id,
                    provider_id=provider_id,
                    api_keys=[], 
                    current_key_index=0,
                    rotation_strategy=rotation_strategy,
                    is_enabled=True,
                    config_data=config_data or {}
                )
                
                self.db.add(new_config)
                await self.db.flush()
                
                new_config.set_api_keys(api_keys)
                await self.db.flush()

                result = {
                    "id": str(new_config.id),
                    "tenant_id": tenant_id,
                    "provider_id": provider_id,
                    "key_count": len(api_keys),
                    "rotation_strategy": rotation_strategy,
                    "is_enabled": True,
                    "action": "created"
                }
                
                logger.info(f"Created tenant provider config for tenant {tenant_id}, provider {provider_id}")
            
            return result
            
        except ValueError:
            raise
        except SQLAlchemyError as e:
            logger.error(f"Database error creating/updating tenant provider config: {e}")
            raise RuntimeError(f"Database error creating/updating provider config: {e}")
        except Exception as e:
            logger.error(f"Failed to create/update tenant provider config: {e}")
            raise RuntimeError(f"Failed to create/update provider config: {e}")
    
    async def get_model_id_by_name(self, model_name: str) -> Optional[str]:
        """
        Get model ID by name
        """
        try:
            result = await self.db.execute(
                select(ProviderModel).where(ProviderModel.model_name == model_name)
            )
            model = result.scalar_one_or_none()

            if not model:
                logger.warning(f"Model {model_name} not found")
                return None

            return str(model.id)
        except SQLAlchemyError as e:
            logger.error(f"Database error getting model ID by name: {e}")
            raise RuntimeError(f"Database error getting model ID by name: {e}")
        except Exception as e:
            logger.error(f"Failed to get model ID by name: {e}")
            raise RuntimeError(f"Failed to get model ID by name: {e}")

    async def get_tenant_provider_config(self, tenant_id: str, provider_id: str) -> Optional[Dict[str, Any]]:
        """
        Get tenant provider configuration (without decrypting API keys)
        """
        try:
            result = await self.db.execute(
                select(TenantProviderConfig).where(
                    and_(
                        TenantProviderConfig.tenant_id == tenant_id,
                        TenantProviderConfig.provider_id == provider_id
                    )
                )
            )
            config = result.scalar_one_or_none()
            
            if not config:
                logger.warning(f"No tenant provider config found for tenant {tenant_id}, provider {provider_id}")
                return None
            
            return {
                "id": str(config.id),
                "tenant_id": tenant_id,
                "provider_id": provider_id,
                "key_count": len(config.api_keys) if config.api_keys else 0,
                "current_key_index": config.current_key_index,
                "rotation_strategy": config.rotation_strategy,
                "is_enabled": config.is_enabled,
                "config_data": config.config_data or {},
                "created_at": config.created_at.isoformat() if config.created_at else None,
                "updated_at": config.updated_at.isoformat() if config.updated_at else None
            }
            
        except SQLAlchemyError as e:
            logger.error(f"Database error getting tenant provider config: {e}")
            raise RuntimeError(f"Database error getting tenant provider config: {e}")
        except Exception as e:
            logger.error(f"Failed to get tenant provider config: {e}")
            raise RuntimeError(f"Failed to get tenant provider config: {e}")
    
    async def add_api_key_to_config(self, tenant_id: str, provider_id: str, new_api_key: str) -> Dict[str, Any]:
        """
        Add new API key to existing tenant provider config
        """
        try:
            result = await self.db.execute(
                select(TenantProviderConfig).where(
                    and_(
                        TenantProviderConfig.tenant_id == tenant_id,
                        TenantProviderConfig.provider_id == provider_id
                    )
                )
            )
            config = result.scalar_one_or_none()
            
            if not config:
                logger.error(f"Tenant provider config not found")
                raise ValueError("Tenant provider config not found")
            
            # Add new encrypted key
            config.add_api_key(new_api_key)  # This encrypts the key
            await self.db.flush()
            
            result = {
                "id": str(config.id),
                "tenant_id": tenant_id,
                "provider_id": provider_id,
                "key_count": len(config.api_keys) if config.api_keys else 0,
                "current_key_index": config.current_key_index,
                "action": "key_added"
            }
            
            logger.info(f"Added API key to tenant {tenant_id}, provider {provider_id}")
            return result
            
        except ValueError:
            raise
        except SQLAlchemyError as e:
            logger.error(f"Database error adding API key: {e}")
            raise RuntimeError(f"Database error adding API key: {e}")
        except Exception as e:
            logger.error(f"Failed to add API key: {e}")
            raise RuntimeError(f"Failed to add API key: {e}")
    
    async def rotate_api_key(self, tenant_id: str, provider_id: str) -> Dict[str, Any]:
        """
        Rotate to next API key for tenant provider config
        """
        try:
            result = await self.db.execute(
                select(TenantProviderConfig).where(
                    and_(
                        TenantProviderConfig.tenant_id == tenant_id,
                        TenantProviderConfig.provider_id == provider_id
                    )
                )
            )
            config = result.scalar_one_or_none()
            
            if not config:
                logger.error(f"Tenant provider config not found")
                raise ValueError("Tenant provider config not found")
            
            new_api_key = config.rotate_to_next_key()
            await self.db.flush()
            
            result = {
                "id": str(config.id),
                "tenant_id": tenant_id,
                "provider_id": provider_id,
                "current_key_index": config.current_key_index,
                "key_count": len(config.api_keys) if config.api_keys else 0,
                "new_api_key": new_api_key,
                "action": "key_rotated"
            }
            
            logger.info(f"Rotated API key for tenant {tenant_id}, provider {provider_id} to index {config.current_key_index}")
            return result
            
        except ValueError:
            raise
        except SQLAlchemyError as e:
            logger.error(f"Database error rotating API key: {e}")
            raise RuntimeError(f"Database error rotating API key: {e}")
        except Exception as e:
            logger.error(f"Failed to rotate API key: {e}")
            raise RuntimeError(f"Failed to rotate API key: {e}")
    
    async def get_available_providers(self) -> List[Dict[str, Any]]:
        """
        Get all available (enabled) providers
        """
        try:
            result = await self.db.execute(
                select(Provider).where(Provider.is_enabled == True)
            )
            providers = result.scalars().all()
            
            result_list = []
            for provider in providers:
                result_list.append({
                    "id": str(provider.id),
                    "provider_name": provider.provider_name,
                    "is_enabled": provider.is_enabled,
                    "base_config": provider.base_config or {}
                })
            
            logger.debug(f"Retrieved {len(result_list)} available providers")
            return result_list
            
        except SQLAlchemyError as e:
            logger.error(f"Database error getting available providers: {e}")
            raise RuntimeError(f"Database error getting available providers: {e}")
        except Exception as e:
            logger.error(f"Failed to get available providers: {e}")
            raise RuntimeError(f"Failed to get available providers: {e}")
    
    async def get_available_models_for_provider(self, provider_id: str) -> List[Dict[str, Any]]:
        """
        Get all available models for a provider
        """
        try:
            result = await self.db.execute(
                select(ProviderModel).where(
                    and_(
                        ProviderModel.provider_id == provider_id,
                        ProviderModel.is_enabled == True
                    )
                )
            )
            models = result.scalars().all()
            
            result_list = []
            for model in models:
                result_list.append({
                    "id": str(model.id),
                    "model_name": model.model_name,
                    "model_type": model.model_type,
                    "provider_id": str(model.provider_id),
                    "is_enabled": model.is_enabled,
                    "model_config": model.model_config or {}
                })
            
            logger.debug(f"Retrieved {len(result_list)} models for provider {provider_id}")
            return result_list
            
        except SQLAlchemyError as e:
            logger.error(f"Database error getting models for provider {provider_id}: {e}")
            raise RuntimeError(f"Database error getting models for provider: {e}")
        except Exception as e:
            logger.error(f"Failed to get models for provider {provider_id}: {e}")
            raise RuntimeError(f"Failed to get models for provider: {e}") 