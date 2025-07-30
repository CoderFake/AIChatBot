"""
Redis Service
Redis client with connection management and error handling
Supports tenant-specific operations and bulk operations
"""
import asyncio
from typing import Dict, Any, List, Optional, Union
import redis.asyncio as redis

from config.settings import get_settings
from utils.logging import get_logger

settings = get_settings()
logger = get_logger(__name__)


class RedisService:
    """
    Redis service with connection pooling and error handling
    Supports tenant-specific caching and bulk operations
    """

    def __init__(self):
        self.redis_pool: Optional[redis.ConnectionPool] = None
        self.redis_client: Optional[redis.Redis] = None
        self._initialized = False
        self._connection_retries = 0
        self._max_retries = 3

    async def initialize(self):
        """Initialize Redis connection pool"""
        try:
            self.redis_pool = redis.ConnectionPool.from_url(
                settings.redis_url,
                max_connections=50,
                retry_on_timeout=True,
                retry_on_error=[redis.ConnectionError, redis.TimeoutError],
                health_check_interval=30,
                socket_connect_timeout=5,
                socket_timeout=5
            )
            
            self.redis_client = redis.Redis(
                connection_pool=self.redis_pool,
                decode_responses=True
            )
            
            await self.redis_client.ping()
            self._initialized = True
            self._connection_retries = 0
            
            logger.info("Redis service initialized successfully")
            
        except Exception as e:
            self._connection_retries += 1
            logger.error(f"Failed to initialize Redis service (attempt {self._connection_retries}): {e}")
            
            if self._connection_retries < self._max_retries:
                await asyncio.sleep(2 ** self._connection_retries) 
                await self.initialize()
            else:
                logger.error("Max Redis connection retries reached")
                raise

    def get_client(self) -> Optional[redis.Redis]:
        """Get Redis client instance"""
        return self.redis_client if self._initialized else None

    async def _ensure_connection(self):
        """Ensure Redis connection is available"""
        if not self._initialized:
            await self.initialize()

    async def ping(self) -> bool:
        """Test Redis connection"""
        try:
            if self.redis_client:
                await self.redis_client.ping()
                return True
        except Exception as e:
            logger.warning(f"Redis ping failed: {e}")
        return False

    async def set_with_retry(
        self, 
        key: str, 
        value: str, 
        ex: Optional[int] = None,
        retries: int = 2
    ) -> bool:
        """Set value with retry logic"""
        for attempt in range(retries + 1):
            try:
                await self._ensure_connection()
                if self.redis_client:
                    if ex:
                        await self.redis_client.setex(key, ex, value)
                    else:
                        await self.redis_client.set(key, value)
                    return True
            except Exception as e:
                logger.warning(f"Redis set attempt {attempt + 1} failed for key {key}: {e}")
                if attempt < retries:
                    await asyncio.sleep(0.5 * (attempt + 1))
                else:
                    logger.error(f"All Redis set attempts failed for key {key}")
        return False

    async def get_with_retry(self, key: str, retries: int = 2) -> Optional[str]:
        """Get value with retry logic"""
        for attempt in range(retries + 1):
            try:
                await self._ensure_connection()
                if self.redis_client:
                    return await self.redis_client.get(key)
            except Exception as e:
                logger.warning(f"Redis get attempt {attempt + 1} failed for key {key}: {e}")
                if attempt < retries:
                    await asyncio.sleep(0.5 * (attempt + 1))
                else:
                    logger.error(f"All Redis get attempts failed for key {key}")
        return None

    async def delete_with_retry(self, *keys: str, retries: int = 2) -> int:
        """Delete keys with retry logic"""
        for attempt in range(retries + 1):
            try:
                await self._ensure_connection()
                if self.redis_client:
                    return await self.redis_client.delete(*keys)
            except Exception as e:
                logger.warning(f"Redis delete attempt {attempt + 1} failed: {e}")
                if attempt < retries:
                    await asyncio.sleep(0.5 * (attempt + 1))
                else:
                    logger.error(f"All Redis delete attempts failed for keys: {keys}")
        return 0

    async def scan_keys(self, pattern: str, count: int = 1000) -> List[str]:
        """Scan keys matching pattern"""
        try:
            await self._ensure_connection()
            if not self.redis_client:
                return []

            keys = []
            cursor = 0
            
            while True:
                cursor, partial_keys = await self.redis_client.scan(
                    cursor=cursor, 
                    match=pattern, 
                    count=count
                )
                keys.extend(partial_keys)
                
                if cursor == 0:
                    break
            
            return keys
            
        except Exception as e:
            logger.error(f"Error scanning keys with pattern {pattern}: {e}")
            return []

    async def delete_key_batch(self, keys: List[str], batch_size: int = 100) -> int:
        """Delete keys in batches"""
        try:
            await self._ensure_connection()
            if not self.redis_client or not keys:
                return 0

            total_deleted = 0
            
            for i in range(0, len(keys), batch_size):
                batch_keys = keys[i:i + batch_size]
                try:
                    deleted = await self.redis_client.delete(*batch_keys)
                    total_deleted += deleted
                except Exception as e:
                    logger.warning(f"Failed to delete batch keys: {e}")
            
            logger.info(f"Deleted {total_deleted} keys from Redis in batches")
            return total_deleted
            
        except Exception as e:
            logger.error(f"Error deleting keys in batches: {e}")
            return 0

    async def delete_all_keys(self) -> int:
        """Delete all keys in current database"""
        try:
            await self._ensure_connection()
            if not self.redis_client:
                return 0

            keys = await self.scan_keys('*')
            
            if keys:
                deleted = await self.delete_key_batch(keys)
                logger.warning(f"Deleted all keys. Total: {deleted} keys")
                return deleted
            
            return 0
            
        except Exception as e:
            logger.error(f"Error deleting all keys: {e}")
            return 0

    async def get_memory_usage(self) -> Dict[str, Any]:
        """Get Redis memory usage information"""
        try:
            await self._ensure_connection()
            if not self.redis_client:
                return {}

            info = await self.redis_client.info('memory')
            return {
                "used_memory": info.get('used_memory', 0),
                "used_memory_human": info.get('used_memory_human', '0B'),
                "used_memory_peak": info.get('used_memory_peak', 0),
                "used_memory_peak_human": info.get('used_memory_peak_human', '0B'),
                "maxmemory": info.get('maxmemory', 0),
                "maxmemory_human": info.get('maxmemory_human', '0B')
            }
            
        except Exception as e:
            logger.error(f"Error getting memory usage: {e}")
            return {}

    async def get_connection_stats(self) -> Dict[str, Any]:
        """Get Redis connection statistics"""
        try:
            await self._ensure_connection()
            if not self.redis_client:
                return {}

            info = await self.redis_client.info('clients')
            return {
                "connected_clients": info.get('connected_clients', 0),
                "client_recent_max_input_buffer": info.get('client_recent_max_input_buffer', 0),
                "client_recent_max_output_buffer": info.get('client_recent_max_output_buffer', 0),
                "blocked_clients": info.get('blocked_clients', 0)
            }
            
        except Exception as e:
            logger.error(f"Error getting connection stats: {e}")
            return {}

    async def health_check(self) -> Dict[str, Any]:
        """Comprehensive Redis health check"""
        health_status = {
            "status": "unknown",
            "ping": False,
            "memory": {},
            "connections": {},
            "error": None
        }
        
        try:
            if await self.ping():
                health_status["ping"] = True
                health_status["status"] = "healthy"
                
                health_status["memory"] = await self.get_memory_usage()
                health_status["connections"] = await self.get_connection_stats()
            else:
                health_status["status"] = "unhealthy"
                health_status["error"] = "Ping failed"
                
        except Exception as e:
            health_status["status"] = "error"
            health_status["error"] = str(e)
            logger.error(f"Redis health check failed: {e}")
        
        return health_status

    async def set_tenant_data(
        self, 
        tenant_id: str, 
        data_type: str, 
        data: Dict[str, Any],
        ttl: Optional[int] = None
    ) -> bool:
        """Set tenant-specific data"""
        key = f"tenant:{tenant_id}:{data_type}"
        import json
        value = json.dumps(data, ensure_ascii=False, default=str)
        return await self.set_with_retry(key, value, ttl)

    async def get_tenant_data(
        self, 
        tenant_id: str, 
        data_type: str
    ) -> Optional[Dict[str, Any]]:
        """Get tenant-specific data"""
        key = f"tenant:{tenant_id}:{data_type}"
        value = await self.get_with_retry(key)
        
        if value:
            try:
                import json
                return json.loads(value)
            except json.JSONDecodeError as e:
                logger.error(f"Failed to decode JSON for key {key}: {e}")
        
        return None

    async def delete_tenant_data(self, tenant_id: str, data_type: Optional[str] = None) -> int:
        """Delete tenant-specific data"""
        if data_type:
            key = f"tenant:{tenant_id}:{data_type}"
            return await self.delete_with_retry(key)
        else:
            pattern = f"tenant:{tenant_id}:*"
            keys = await self.scan_keys(pattern)
            if keys:
                return await self.delete_key_batch(keys)
        return 0

    async def get_tenant_cache_keys(self, tenant_id: str) -> List[str]:
        """Get all cache keys for specific tenant"""
        pattern = f"tenant:{tenant_id}:*"
        return await self.scan_keys(pattern)

    async def close(self):
        """Close Redis connections"""
        try:
            if self.redis_client:
                await self.redis_client.close()
            if self.redis_pool:
                await self.redis_pool.disconnect()
            
            self._initialized = False
            logger.info("Redis service connections closed")
            
        except Exception as e:
            logger.error(f"Error closing Redis connections: {e}")

redis_client = RedisService()