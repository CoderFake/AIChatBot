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

class ProgressService:
    """
    Service layer for document progress operations
    Handles progress retrieval, caching, and business logic
    """

    def __init__(self):
        from services.cache.cache_manager import cache_manager
        self._cache_manager = cache_manager

    async def get_document_progress(
        self,
        tenant_id: str,
        department_id: str,
        document_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        Get latest progress for a specific document
        """
        try:
            cache_key = f"progress:{tenant_id}:{department_id}:{document_id}"
            cached_data = await self._cache_manager.get(cache_key)

            if cached_data:
                return {
                    "progress": cached_data.get("progress", 0),
                    "status": cached_data.get("status", "unknown"),
                    "message": cached_data.get("message", ""),
                    "timestamp": cached_data.get("timestamp"),
                    "extra": cached_data.get("extra", {})
                }

            logger.debug(f"No cached progress found for document {document_id}")
            return None

        except Exception as e:
            logger.error(f"Failed to get document progress: {e}")
            return None

    async def get_batch_progress(
        self,
        tenant_id: str,
        department_id: str,
        batch_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        Get latest progress for a batch operation
        """
        try:
            cache_key = f"progress:{tenant_id}:{department_id}:{batch_id}"
            cached_data = await self._cache_manager.get(cache_key)

            if cached_data:
                return {
                    "progress": cached_data.get("progress", 0),
                    "status": cached_data.get("status", "unknown"),
                    "message": cached_data.get("message", ""),
                    "timestamp": cached_data.get("timestamp"),
                    "extra": cached_data.get("extra", {})
                }

            logger.debug(f"No cached progress found for batch {batch_id}")
            return None

        except Exception as e:
            logger.error(f"Failed to get batch progress: {e}")
            return None

    async def get_realtime_progress(
        self,
        tenant_id: str,
        department_id: str
    ) -> List[Dict[str, Any]]:
        """
        Get latest progress updates for all user's documents
        Note: This is a simplified implementation. For production,
        consider using Redis SCAN or a dedicated progress store.
        """
        try:
            user_progress = []

            # For now, return a placeholder. In production, you'd need to
            # implement a way to scan Redis keys with pattern matching
            # or maintain an index of progress keys per tenant.
            # Pattern would be: f"progress:{tenant_id}:{department_id}:*"

            logger.debug(f"Realtime progress requested for {tenant_id}:{department_id}")
            logger.info("Realtime progress scanning not yet implemented - returning empty list")

            return user_progress

        except Exception as e:
            logger.error(f"Failed to get realtime progress: {e}")
            return []

    async def update_progress_cache(self, tenant_id: str, department_id: str, document_id: Optional[str], progress_data: Dict[str, Any]):
        """Update progress cache (called by Kafka service when publishing)"""
        cache_key = f"progress:{tenant_id}:{department_id}:{document_id or 'batch'}"
        await self._cache_manager.set_dict(cache_key, progress_data, ttl=3600)  # Cache for 1 hour

    async def clear_progress_cache(self, tenant_id: Optional[str] = None, department_id: Optional[str] = None):
        """Clear progress cache (optionally filtered by tenant/department)"""
        try:
            if tenant_id and department_id:
                pattern = f"progress:{tenant_id}:{department_id}:*"
                deleted_count = await self._cache_manager.delete_pattern(pattern)
                logger.info(f"Cleared {deleted_count} progress cache keys for tenant {tenant_id}, dept {department_id}")
            else:
                # Clear all progress keys (dangerous, use with caution)
                pattern = "progress:*"
                deleted_count = await self._cache_manager.delete_pattern(pattern)
                logger.warning(f"Cleared {deleted_count} total progress cache keys")
        except Exception as e:
            logger.error(f"Failed to clear progress cache: {e}")

progress_service = ProgressService()

class DocumentProgressService:
    """
    Service layer for document progress operations
    Handles progress retrieval and business logic for API endpoints
    """

    def __init__(self):
        self._progress_service = progress_service

    async def get_document_progress(self, tenant_id: str, department_id: str, document_id: str, db):
        """
        Get document progress with document validation
        For admin users, department_id might be None, so we get it from document
        """
        try:
            actual_department_id = department_id
            if not actual_department_id:
                from models.database.document import Document
                from sqlalchemy import select

                result = await db.execute(
                    select(Document).where(Document.id == document_id)
                )
                document = result.scalar_one_or_none()

                if not document:
                    return {"error": "Document not found", "status_code": 404}

                actual_department_id = str(document.department_id)

            progress_data = await self._progress_service.get_document_progress(
                tenant_id=tenant_id,
                department_id=actual_department_id,
                document_id=document_id
            )

            if progress_data:
                return {
                    "document_id": document_id,
                    "progress": progress_data.get("progress", 0),
                    "status": progress_data.get("status", "unknown"),
                    "message": progress_data.get("message", ""),
                    "timestamp": progress_data.get("timestamp"),
                    "extra": progress_data.get("extra", {})
                }
            else:
                if not actual_department_id:
                    from models.database.document import Document
                    from sqlalchemy import select

                    result = await db.execute(
                        select(Document).where(Document.id == document_id)
                    )
                    document = result.scalar_one_or_none()

                    if document:
                        return {
                            "document_id": document_id,
                            "progress": 0,
                            "status": document.processing_status or "unknown",
                            "message": f"Document status: {document.processing_status or 'unknown'}",
                            "timestamp": document.created_at.isoformat() if document.created_at else None,
                            "extra": {}
                        }

                return {
                    "document_id": document_id,
                    "progress": 0,
                    "status": "unknown",
                    "message": "No progress data available",
                    "timestamp": None,
                    "extra": {}
                }

        except Exception as e:
            logger.error(f"Failed to get document progress: {e}")
            return {"error": str(e), "status_code": 500}

    async def get_batch_progress(self, tenant_id: str, department_id: str, batch_id: str):
        """
        Get batch progress
        """
        try:
            progress_data = await self._progress_service.get_batch_progress(
                tenant_id=tenant_id,
                department_id=department_id,
                batch_id=batch_id
            )

            if progress_data:
                return {
                    "batch_id": batch_id,
                    "progress": progress_data.get("progress", 0),
                    "status": progress_data.get("status", "unknown"),
                    "message": progress_data.get("message", ""),
                    "timestamp": progress_data.get("timestamp"),
                    "extra": progress_data.get("extra", {})
                }
            else:
                return {
                    "batch_id": batch_id,
                    "progress": 0,
                    "status": "unknown",
                    "message": "No progress data available",
                    "timestamp": None,
                    "extra": {}
                }

        except Exception as e:
            logger.error(f"Failed to get batch progress: {e}")
            return {"error": str(e), "status_code": 500}

    async def get_realtime_progress(self, tenant_id: str, department_id: str):
        """
        Get realtime progress for all user's documents
        """
        try:
            progress_updates = await self._progress_service.get_realtime_progress(
                tenant_id=tenant_id,
                department_id=department_id
            )

            return {
                "tenant_id": tenant_id,
                "department_id": department_id,
                "updates": progress_updates,
                "timestamp": datetime.utcnow().isoformat()
            }

        except Exception as e:
            logger.error(f"Failed to get realtime progress: {e}")
            return {"error": str(e), "status_code": 500}


document_progress_service = DocumentProgressService()


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

            # Store in cache for quick retrieval via progress service
            await progress_service.update_progress_cache(tenant_id, department_id, document_id, payload)

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
    
    async def get_document_progress(
        self,
        tenant_id: str,
        department_id: str,
        document_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        Get latest progress for a specific document
        Returns the most recent progress message from Kafka topic
        """
        if not AIOKAFKA_AVAILABLE:
            logger.info(f"Kafka get progress skipped - aiokafka not available for document {document_id}")
            return None

        try:
            if not self._is_consumer_running:
                logger.info("Starting consumer for progress retrieval")
                await self.start_consumer(lambda msg: None, [self._document_topic])

            await asyncio.sleep(0.1)

            if self._consumer:
                found_message = None
                try:
                    async for message in self._consumer:
                        try:
                            msg_data = message.value
                            if isinstance(msg_data, dict):
                                if (msg_data.get('tenant_id') == tenant_id and
                                    msg_data.get('department_id') == department_id and
                                    msg_data.get('document_id') == document_id):
                                    found_message = {
                                        "progress": msg_data.get("progress", 0),
                                        "status": msg_data.get("status", "unknown"),
                                        "message": msg_data.get("message", ""),
                                        "timestamp": msg_data.get("timestamp"),
                                        "extra": msg_data.get("extra", {})
                                    }
                                    logger.debug(f"Found progress message for document {document_id}: {found_message}")
                                    break
                        except Exception as e:
                            logger.debug(f"Error processing message: {e}")
                            continue

                        await asyncio.sleep(0.01)

                    if found_message:
                        return found_message
                    else:
                        logger.debug(f"No progress message found for document {document_id}")
                        return None

                except Exception as e:
                    logger.error(f"Error consuming messages for document {document_id}: {e}")
                    return None

            else:
                logger.warning("Consumer not available for progress retrieval")
                return None

        except Exception as e:
            logger.error(f"Failed to get document progress for {document_id}: {e}")
            return None

    async def get_batch_progress(
        self,
        tenant_id: str,
        department_id: str,
        batch_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        Get latest progress for a batch operation
        Returns the most recent batch progress message from Kafka
        """
        if not AIOKAFKA_AVAILABLE:
            logger.info(f"Kafka get batch progress skipped - aiokafka not available for batch {batch_id}")
            return None

        try:
            if not self._is_consumer_running:
                logger.info("Starting consumer for batch progress retrieval")
                await self.start_consumer(lambda msg: None, [self._document_topic])

            await asyncio.sleep(0.1)

            if self._consumer:
                found_message = None
                try:
                    async for message in self._consumer:
                        try:
                            msg_data = message.value
                            if isinstance(msg_data, dict):
                                if (msg_data.get('tenant_id') == tenant_id and
                                    msg_data.get('department_id') == department_id and
                                    msg_data.get('extra', {}).get('batch_id') == batch_id):
                                    found_message = {
                                        "batch_id": batch_id,
                                        "progress": msg_data.get("progress", 0),
                                        "status": msg_data.get("status", "unknown"),
                                        "message": msg_data.get("message", ""),
                                        "timestamp": msg_data.get("timestamp"),
                                        "extra": msg_data.get("extra", {})
                                    }
                                    logger.debug(f"Found batch progress message for {batch_id}: {found_message}")
                                    break
                        except Exception as e:
                            logger.debug(f"Error processing message: {e}")
                            continue

                        await asyncio.sleep(0.01)

                    if found_message:
                        return found_message
                    else:
                        logger.debug(f"No batch progress message found for batch {batch_id}")
                        return None

                except Exception as e:
                    logger.error(f"Error consuming messages for batch {batch_id}: {e}")
                    return None

            else:
                logger.warning("Consumer not available for batch progress retrieval")
                return None

        except Exception as e:
            logger.error(f"Failed to get batch progress for {batch_id}: {e}")
            return None

    async def get_realtime_progress(
        self,
        tenant_id: str,
        department_id: str
    ) -> List[Dict[str, Any]]:
        """
        Get latest progress updates for all user's documents
        Returns recent progress messages from Kafka for the tenant/department
        """
        if not AIOKAFKA_AVAILABLE:
            logger.info("Kafka get realtime progress skipped - aiokafka not available")
            return []

        try:
            if not self._is_consumer_running:
                logger.info("Starting consumer for realtime progress retrieval")
                await self.start_consumer(lambda msg: None, [self._document_topic])

            await asyncio.sleep(0.1)

            if self._consumer:
                progress_updates = []
                message_count = 0

                try:
                    async for message in self._consumer:
                        try:
                            msg_data = message.value
                            if isinstance(msg_data, dict):
                                if (msg_data.get('tenant_id') == tenant_id and
                                    msg_data.get('department_id') == department_id):
                                    progress_update = {
                                        "document_id": msg_data.get("document_id"),
                                        "batch_id": msg_data.get("extra", {}).get("batch_id"),
                                        "progress": msg_data.get("progress", 0),
                                        "status": msg_data.get("status", "unknown"),
                                        "message": msg_data.get("message", ""),
                                        "timestamp": msg_data.get("timestamp"),
                                        "extra": msg_data.get("extra", {})
                                    }
                                    progress_updates.append(progress_update)
                                    message_count += 1

                                    if message_count >= 50:
                                        break
                        except Exception as e:
                            logger.debug(f"Error processing message: {e}")
                            continue

                        await asyncio.sleep(0.005)

                    progress_updates.sort(key=lambda x: x.get("timestamp", ""), reverse=True)

                    logger.debug(f"Retrieved {len(progress_updates)} progress updates for {tenant_id}:{department_id}")
                    return progress_updates

                except Exception as e:
                    logger.error(f"Error consuming messages for realtime progress: {e}")
                    return []

            else:
                logger.warning("Consumer not available for realtime progress retrieval")
                return []

        except Exception as e:
            logger.error(f"Failed to get realtime progress for {tenant_id}:{department_id}: {e}")
            return []

    async def cleanup(self) -> None:
        """Cleanup Kafka resources"""
        await self.stop_consumer()
        await self.stop_producer()
        logger.info("Kafka service cleanup completed")


kafka_service = KafkaService() 