import redis
from utils.logging import get_logger
from config.settings import get_settings

settings = get_settings()

logger = get_logger(__name__)


class RedisService:
    """
    Redis service
    - Get cache
    - Set cache
    - Delete cache
    - Chat session cache for anonymous (default 1 hour)
    - Chat history cache for anonymous (default 1 hour)
    - Chat message cache for anonymous (default 1 hour)
    - LangGraph agent cache (no limit)
    - LangGraph tool cache (no limit)
    - LangGraph workflow cache(state, result, etc) (no limit)
    - Model cache(model name, model embedding, model tokenizer) (no limit)
    - Other config cache(provider key,...)(no limit)
    """

    def __init__(self):
        self.redis_pool = None
        self.redis_client = None

    def get_client(self):
        try:
            if self.redis_pool is None:
                self.redis_pool = redis.ConnectionPool(
                    host=settings.REDIS_HOST,
                    port=settings.REDIS_PORT,
                    db=settings.REDIS_DB,
                    max_connections=10
                )
            if self.redis_client is None:
                self.redis_client = redis.StrictRedis(connection_pool=self.redis_pool)
            return self.redis_client
        except Exception as e:
            logger.error(f"Error initializing Redis client: {e}")
            raise

    def scan_keys(self, pattern):
        try:
            if self.redis_client is None:
                self.get_client()

            cursor = '0'
            keys = []
            while cursor != 0:
                cursor, partial_keys = self.redis_client.scan(cursor=cursor, match=pattern, count=1000)
                keys.extend(partial_keys)
            return keys
        except Exception as e:
            logger.error(f"Error scanning keys: {e}")
            raise

    def delete_key_batch(self, keys):
        try:
            if self.redis_client is None:
                self.get_client()
            pipeline = self.redis_client.pipeline()
            for key in keys:
                pipeline.delete(key)
            pipeline.execute()
            logger.info(f"Deleted {len(keys)} keys from Redis.")
        except Exception as e:
            logger.error(f"Error deleting keys: {e}")
            raise

    def delete_all_keys(self):
        try:
            if self.redis_client is None:
                self.get_client()
            keys = self.redis_client.keys('*')
            if keys:
                self.redis_client.delete(*keys)
                logger.info(f"Deleted all keys. Total: {len(keys)} keys.")
                return len(keys)
            return 0
        except Exception as e:
            logger.error(f"Error deleting all keys: {e}")
            raise

redis_client = RedisService()