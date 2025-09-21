"""
Cache Manager Service
Central cache management with Redis primary and Memory fallback
Handles tenant-specific caching and Redis operations
"""
import json
import asyncio
from typing import Dict, Any, Optional

from services.cache.redis_service import redis_client
from config.settings import get_settings
from utils.logging import get_logger
from utils.datetime_utils import  DateTimeManager

logger = get_logger(__name__)
settings = get_settings()


class CacheManager:
    """
    Central cache manager with Redis backend and in-memory fallback
    Handles tenant-specific caching without expiration unless signaled
    """
    
    def __init__(self):
        self._fallback_cache = {}
        logger.info("Using dict as fallback cache")

        self._cache_stats = {
            "hits": 0,
            "misses": 0,
            "sets": 0,
            "deletes": 0,
            "errors": 0
        }
        self._initialized = False
    
    async def initialize(self):
        """Initialize cache manager and Redis connection"""
        try:
            await redis_client.initialize()
            client = redis_client.get_client()
            if client:
                await client.ping()
            self._initialized = True
            logger.info("Cache manager initialized successfully")

        except Exception as e:
            logger.warning(f"Redis unavailable, using fallback cache: {e}")
            self._initialized = True
    
    async def _ensure_initialized(self):
        """Ensure cache manager is initialized"""
        if not self._initialized:
            await self.initialize()
    
    async def get(self, key: str, default: Any = None) -> Any:
        """
        Get value from cache with Redis primary, fallback to in-memory
        
        Args:
            key: Cache key
            default: Default value if not found
            
        Returns:
            Cached value or default
        """
        await self._ensure_initialized()
        
        try:
            try:
                await redis_client._ensure_connection()
                client = redis_client.get_client()
                if client:
                    value = await client.get(key)
                    if value is not None:
                        self._cache_stats["hits"] += 1
                        return json.loads(value)
            except Exception as redis_error:
                logger.warning(f"Redis get error for key {key}: {redis_error}")
                if "Connection refused" in str(redis_error) or "ConnectionError" in str(redis_error):
                    redis_client._initialized = False

            # Dict fallback only
            if key in self._fallback_cache:
                self._cache_stats["hits"] += 1
                logger.debug(f"Cache hit (dict fallback): {key}")
                return self._fallback_cache[key]

            self._cache_stats["misses"] += 1
            logger.debug(f"Cache miss: {key}")
            return default
            
        except Exception as e:
            logger.error(f"Cache get error for key {key}: {e}")
            self._cache_stats["errors"] += 1
            return default
    
    async def set(
        self, 
        key: str, 
        value: Any, 
        ttl: Optional[int] = None,
        serialize: bool = True
    ) -> bool:
        """
        Set value in cache
        
        Args:
            key: Cache key
            value: Value to cache
            ttl: Time to live in seconds (None for no expiration)
            serialize: Whether to JSON serialize the value
            
        Returns:
            True if successful, False otherwise
        """
        await self._ensure_initialized()
        
        try:
            cache_value = json.dumps(value, ensure_ascii=False, default=str) if serialize else value
            
            try:
                await redis_client._ensure_connection()
                client = redis_client.get_client()
                if client:
                    if ttl:
                        await client.setex(key, ttl, cache_value)
                    else:
                        await client.set(key, cache_value)

                    self._cache_stats["sets"] += 1
                    logger.debug(f"Cache set (Redis): {key}")
                    return True

            except Exception as redis_error:
                logger.warning(f"Redis set error for key {key}: {redis_error}")
                # Reset initialization flag on connection errors
                if "Connection refused" in str(redis_error) or "ConnectionError" in str(redis_error):
                    redis_client._initialized = False

            # Dict fallback only
            self._fallback_cache[key] = value
            self._cache_stats["sets"] += 1
            logger.debug(f"Cache set (dict fallback): {key}")
            return True
            
        except Exception as e:
            logger.error(f"Cache set error for key {key}: {e}")
            self._cache_stats["errors"] += 1
            return False

    async def set_dict(
        self,
        key: str,
        value: Dict[str, Any],
        ttl: Optional[int] = None
    ) -> bool:
        """
        Set dictionary value in cache

        Args:
            key: Cache key
            value: Dictionary to cache
            ttl: Time to live in seconds (None for no expiration)

        Returns:
            True if successful, False otherwise
        """
        return await self.set(key, value, ttl, serialize=True)

    async def delete(self, key: str) -> bool:
        """
        Delete value from cache
        
        Args:
            key: Cache key to delete
            
        Returns:
            True if successful, False otherwise
        """
        await self._ensure_initialized()
        
        try:
            success = False
            
            try:
                await redis_client._ensure_connection()
                client = redis_client.get_client()
                if client:
                    result = await client.delete(key)
                    success = result > 0
            except Exception as redis_error:
                logger.warning(f"Redis delete error for key {key}: {redis_error}")

            if key in self._fallback_cache:
                del self._fallback_cache[key]
                success = True
            
            if success:
                self._cache_stats["deletes"] += 1
                logger.debug(f"Cache delete: {key}")
            
            return success
            
        except Exception as e:
            logger.error(f"Cache delete error for key {key}: {e}")
            self._cache_stats["errors"] += 1
            return False
    
    async def delete_pattern(self, pattern: str) -> int:
        """
        Delete keys matching pattern
        
        Args:
            pattern: Key pattern (e.g., "tenant:123:*")
            
        Returns:
            Number of keys deleted
        """
        await self._ensure_initialized()
        
        try:
            deleted_count = 0
            
            try:
                await redis_client._ensure_connection()
                client = redis_client.get_client()
                if client:
                    keys = await client.keys(pattern)
                    if keys:
                        deleted_count = await client.delete(*keys)
                        logger.debug(f"Deleted {deleted_count} Redis keys matching pattern: {pattern}")
            except Exception as redis_error:
                logger.warning(f"Redis pattern delete error for {pattern}: {redis_error}")
            
            fallback_keys = [key for key in self._fallback_cache.keys() if self._match_pattern(key, pattern)]
            for key in fallback_keys:
                del self._fallback_cache[key]

            deleted_count += len(fallback_keys)
            
            if deleted_count > 0:
                self._cache_stats["deletes"] += deleted_count
                logger.info(f"Deleted {deleted_count} keys matching pattern: {pattern}")
            
            return deleted_count
            
        except Exception as e:
            logger.error(f"Cache pattern delete error for {pattern}: {e}")
            self._cache_stats["errors"] += 1
            return 0
    
    def _match_pattern(self, key: str, pattern: str) -> bool:
        """Simple pattern matching for fallback cache"""
        if pattern.endswith("*"):
            return key.startswith(pattern[:-1])
        return key == pattern
    
    async def exists(self, key: str) -> bool:
        """
        Check if key exists in cache
        
        Args:
            key: Cache key to check
            
        Returns:
            True if key exists, False otherwise
        """
        await self._ensure_initialized()
        
        try:
            try:
                await redis_client._ensure_connection()
                client = redis_client.get_client()
                if client:
                    exists = await client.exists(key)
                    if exists:
                        return True
            except Exception as redis_error:
                logger.warning(f"Redis exists error for key {key}: {redis_error}")

            return key in self._fallback_cache
            
        except Exception as e:
            logger.error(f"Cache exists error for key {key}: {e}")
            return False
    
    async def get_or_set(
        self, 
        key: str, 
        value_func, 
        ttl: Optional[int] = None,
        *args, 
        **kwargs
    ) -> Any:
        """
        Get value from cache or set it using provided function
        
        Args:
            key: Cache key
            value_func: Function to call if cache miss (can be async)
            ttl: Time to live in seconds
            *args, **kwargs: Arguments for value_func
            
        Returns:
            Cached or computed value
        """
        cached_value = await self.get(key)
        if cached_value is not None:
            return cached_value
        
        try:
            if asyncio.iscoroutinefunction(value_func):
                computed_value = await value_func(*args, **kwargs)
            else:
                computed_value = value_func(*args, **kwargs)
            
            await self.set(key, computed_value, ttl)
            return computed_value
            
        except Exception as e:
            logger.error(f"Error computing value for cache key {key}: {e}")
            return None
    
    async def get_tenant_cache_key(self, tenant_id: str, cache_type: str) -> str:
        """
        Generate tenant-specific cache key
        
        Args:
            tenant_id: Tenant identifier
            cache_type: Type of cache (providers, agents, tools, permissions)
            
        Returns:
            Formatted cache key
        """
        return f"tenant:{tenant_id}:{cache_type}"
    
    async def invalidate_tenant_cache(self, tenant_id: str) -> int:
        """
        Invalidate all cache for specific tenant
        
        Args:
            tenant_id: Tenant identifier
            
        Returns:
            Number of keys invalidated
        """
        pattern = f"tenant:{tenant_id}:*"
        deleted_count = await self.delete_pattern(pattern)
        logger.info(f"Invalidated {deleted_count} cache keys for tenant {tenant_id}")
        return deleted_count
    
    async def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        await self._ensure_initialized()
        
        redis_info = {}
        try:
            await redis_client._ensure_connection()
            client = redis_client.get_client()
            if client:
                redis_info = await client.info()
        except Exception as e:
            logger.warning(f"Could not get Redis info: {e}")
        

            fallback_size = len(self._fallback_cache)

        return {
            "stats": self._cache_stats.copy(),
            "fallback_cache_size": fallback_size,
            "fallback_cache_type": "dict",
            "redis_available": redis_client.get_client() is not None,
            "redis_info": redis_info,
            "initialized": self._initialized
        }
    
    async def health_check(self) -> Dict[str, Any]:
        """Perform cache health check"""
        await self._ensure_initialized()
        
        health_status = {
            "cache_manager": "healthy",
            "redis": "unknown",
            "fallback": "healthy",
            "overall": "healthy"
        }
        
        try:
            await redis_client._ensure_connection()
            client = redis_client.get_client()
            if client:
                test_key = f"health_check_{DateTimeManager.system_now().timestamp()}"
                await client.set(test_key, "test", ex=10)
                value = await client.get(test_key)
                await client.delete(test_key)

                if value == "test":
                    health_status["redis"] = "healthy"
                else:
                    health_status["redis"] = "unhealthy"
                    health_status["overall"] = "degraded"
            else:
                health_status["redis"] = "unavailable"
                health_status["overall"] = "degraded"
                
        except Exception as e:
            logger.warning(f"Redis health check failed: {e}")
            health_status["redis"] = "unhealthy"
            health_status["overall"] = "degraded"
        
        return health_status
    
    async def clear_all(self) -> bool:
        """Clear all cache (use with caution)"""
        await self._ensure_initialized()
        
        try:
            success = True
            
            try:
                await redis_client._ensure_connection()
                client = redis_client.get_client()
                if client:
                    await client.flushdb()
                    logger.warning("Cleared all Redis cache")
                else:
                    logger.warning("Redis client not available")
            except Exception as redis_error:
                logger.error(f"Failed to clear Redis cache: {redis_error}")
                success = False
            
            self._fallback_cache.clear()
            logger.warning("Cleared dict fallback cache")
            
            self._cache_stats = {
                "hits": 0,
                "misses": 0,
                "sets": 0,
                "deletes": 0,
                "errors": 0
            }
            
            return success
            
        except Exception as e:
            logger.error(f"Failed to clear all cache: {e}")
            return False


cache_manager = CacheManager()