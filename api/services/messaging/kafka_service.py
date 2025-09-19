"""
Kafka Service for document processing messages
Handles async producer/consumer with proper error handling and reconnection
"""
from typing import Optional, Dict, Any, Callable, List
import asyncio
import json
from datetime import datetime
from utils.logging import get_logger
from config.settings import get_settings

logger = get_logger(__name__)
settings = get_settings()

try:
    from aiokafka import AIOKafkaProducer, AIOKafkaConsumer
    AIOKAFKA_AVAILABLE = True
except ImportError:
    AIOKAFKA_AVAILABLE = False
    logger.warning("aiokafka not available - Kafka functionality disabled")


class KafkaService:
    """
    Kafka service for document processing messages with async producer/consumer
    """
    
    def __init__(self):
        self._producer: Optional[AIOKafkaProducer] = None
        self._consumer: Optional[AIOKafkaConsumer] = None
        self._is_producer_running = False
        self._is_consumer_running = False
        
        # Get settings from config
        self._bootstrap_servers = settings.KAFKA_BOOTSTRAP_SERVERS
        self._document_topic = settings.KAFKA_DOCUMENT_TOPIC
        self._consumer_group = settings.KAFKA_CONSUMER_GROUP
        
        if not AIOKAFKA_AVAILABLE:
            logger.warning("Kafka service initialized but aiokafka not available")
    
    async def start_producer(self) -> None:
        """Start Kafka producer"""
        if not AIOKAFKA_AVAILABLE:
            logger.info("Kafka producer start skipped - aiokafka not available")
            return
            
        if self._is_producer_running:
            return
            
        try:
            self._producer = AIOKafkaProducer(
                bootstrap_servers=self._bootstrap_servers,
                value_serializer=lambda v: json.dumps(v, ensure_ascii=False, default=str).encode('utf-8'),
                key_serializer=lambda k: k.encode('utf-8') if k else None,
                retry_backoff_ms=1000,
                request_timeout_ms=30000,
                max_request_size=1048576,  # 1MB
                compression_type='gzip'
            )
            
            await self._producer.start()
            self._is_producer_running = True
            logger.info(f"Kafka producer started - servers: {self._bootstrap_servers}")
            
        except Exception as e:
            logger.error(f"Failed to start Kafka producer: {e}")
            self._producer = None
            raise
    
    async def stop_producer(self) -> None:
        """Stop Kafka producer"""
        if self._producer and self._is_producer_running:
            try:
                await self._producer.stop()
                logger.info("Kafka producer stopped")
            except Exception as e:
                logger.error(f"Error stopping Kafka producer: {e}")
            finally:
                self._producer = None
                self._is_producer_running = False
    
    async def publish_document_progress(
        self, 
        tenant_id: str,
        department_id: str, 
        document_id: Optional[str],
        progress: int,
        status: str,
        message: str,
        extra: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Publish document processing progress to Kafka
        
        Args:
            tenant_id: Tenant ID
            department_id: Department ID  
            document_id: Document ID (can be None for batch operations)
            progress: Progress percentage (0-100)
            status: Status (pending|processing|completed|failed|completed_with_errors)
            message: Human readable message
            extra: Additional metadata
            
        Returns:
            True if published successfully, False otherwise
        """
        if not AIOKAFKA_AVAILABLE:
            logger.info(f"Kafka progress (skipped): {tenant_id}/{department_id}/{document_id} - {progress}% - {status}: {message}")
            return False
            
        if not self._is_producer_running:
            await self.start_producer()
            
        if not self._producer:
            logger.warning("Kafka producer not available")
            return False
            
        try:
            payload = {
                "timestamp": datetime.utcnow().isoformat(),
                "tenant_id": tenant_id,
                "department_id": department_id,
                "document_id": document_id,
                "progress": max(0, min(100, progress)), 
                "status": status,
                "message": message,
                "service": "document_service"
            }
            
            if extra:
                payload.update(extra)
            
            key = f"{tenant_id}_{department_id}"
            
            await self._producer.send_and_wait(
                topic=self._document_topic,
                value=payload,
                key=key
            )
            
            logger.debug(f"Published document progress: {tenant_id}/{document_id} - {progress}%")
            return True
            
        except Exception as e:
            logger.error(f"Failed to publish document progress: {e}")
            return False
    
    async def start_consumer(
        self, 
        message_handler: Callable[[Dict[str, Any]], None],
        topics: Optional[List[str]] = None
    ) -> None:
        """
        Start Kafka consumer with message handler
        
        Args:
            message_handler: Async function to handle received messages
            topics: List of topics to subscribe (defaults to document topic)
        """
        if not AIOKAFKA_AVAILABLE:
            logger.info("Kafka consumer start skipped - aiokafka not available")
            return
            
        if self._is_consumer_running:
            return
            
        consumer_topics = topics or [self._document_topic]
        
        try:
            self._consumer = AIOKafkaConsumer(
                *consumer_topics,
                bootstrap_servers=self._bootstrap_servers,
                group_id=self._consumer_group,
                value_deserializer=lambda m: json.loads(m.decode('utf-8')),
                key_deserializer=lambda k: k.decode('utf-8') if k else None,
                auto_offset_reset='latest',
                enable_auto_commit=True,
                auto_commit_interval_ms=1000,
                max_poll_records=100
            )
            
            await self._consumer.start()
            self._is_consumer_running = True
            logger.info(f"Kafka consumer started - topics: {consumer_topics}, group: {self._consumer_group}")
            
            asyncio.create_task(self._consume_messages(message_handler))
            
        except Exception as e:
            logger.error(f"Failed to start Kafka consumer: {e}")
            self._consumer = None
            raise
    
    async def _consume_messages(self, message_handler: Callable[[Dict[str, Any]], None]) -> None:
        """Internal method to consume messages"""
        if not self._consumer:
            return
            
        try:
            async for message in self._consumer:
                try:
                    await message_handler(message.value)
                except Exception as e:
                    logger.error(f"Error handling Kafka message: {e}")
                    
        except Exception as e:
            logger.error(f"Error in Kafka message consumption: {e}")
    
    async def stop_consumer(self) -> None:
        """Stop Kafka consumer"""
        if self._consumer and self._is_consumer_running:
            try:
                await self._consumer.stop()
                logger.info("Kafka consumer stopped")
            except Exception as e:
                logger.error(f"Error stopping Kafka consumer: {e}")
            finally:
                self._consumer = None
                self._is_consumer_running = False
    
    async def publish_batch_progress(
        self,
        tenant_id: str,
        department_id: str,
        batch_id: str,
        total_files: int,
        completed_files: int,
        failed_files: int,
        status: str,
        message: str
    ) -> bool:
        """
        Publish batch upload progress
        """
        progress = int((completed_files + failed_files) * 100 / max(1, total_files))
        
        return await self.publish_document_progress(
            tenant_id=tenant_id,
            department_id=department_id,
            document_id=None,
            progress=progress,
            status=status,
            message=message,
            extra={
                "batch_id": batch_id,
                "total_files": total_files,
                "completed_files": completed_files,
                "failed_files": failed_files,
                "operation": "batch_upload"
            }
        )
    
    async def health_check(self) -> Dict[str, Any]:
        """Check Kafka service health"""
        return {
            "kafka_available": AIOKAFKA_AVAILABLE,
            "producer_running": self._is_producer_running,
            "consumer_running": self._is_consumer_running,
            "bootstrap_servers": self._bootstrap_servers,
            "document_topic": self._document_topic,
            "consumer_group": self._consumer_group
        }
    
    async def cleanup(self) -> None:
        """Cleanup Kafka resources"""
        await self.stop_consumer()
        await self.stop_producer()
        logger.info("Kafka service cleanup completed")


kafka_service = KafkaService() 