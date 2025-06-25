from typing import Dict, Any, List, Optional, Callable
from datetime import datetime, timedelta
import asyncio
from dataclasses import dataclass
from enum import Enum

from config.settings import get_settings
from utils.logging import get_logger

logger = get_logger(__name__)

class MonitoringEventType(Enum):
    CONFIG_CHANGE = "config_change"
    DATA_STALENESS = "data_staleness"
    UPDATE_REQUIRED = "update_required"
    PERFORMANCE_ISSUE = "performance_issue"

class UpdateStatus(Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"

@dataclass
class MonitoringEvent:
    """Unified monitoring event"""
    timestamp: datetime
    event_type: MonitoringEventType
    component: str
    severity: str
    data: Dict[str, Any]
    source: str

@dataclass
class UpdateTask:
    """Update task definition"""
    id: str
    component: str
    update_type: str
    config: Dict[str, Any]
    priority: int
    status: UpdateStatus
    scheduled_at: datetime
    attempts: int = 0

class UnifiedWorkflowMonitor:
    """
    Unified monitoring component cho workflows
    Gộp change detection, freshness monitoring và update pipeline
    """
    
    def __init__(self):
        self.settings = get_settings()
        self._monitoring_enabled = True
        
        # Event tracking
        self._event_history: List[MonitoringEvent] = []
        self._event_subscribers: Dict[str, List[Callable]] = {}
        
        # Change detection
        self._change_history: List[MonitoringEvent] = []
        self._config_cache: Dict[str, Any] = {}
        
        # Freshness monitoring  
        self._freshness_data: Dict[str, datetime] = {}
        self._staleness_thresholds: Dict[str, timedelta] = {
            "vector_index": timedelta(hours=24),
            "config_cache": timedelta(minutes=30),
            "user_permissions": timedelta(hours=4),
            "document_metadata": timedelta(hours=12)
        }
        
        # Update pipeline
        self._update_queue: List[UpdateTask] = []
        self._active_updates: Dict[str, UpdateTask] = {}
        
    async def start_monitoring(self):
        """Start unified monitoring"""
        logger.info("Starting unified workflow monitoring")
        self._monitoring_enabled = True
        
        # Start monitoring tasks
        monitoring_tasks = [
            self._config_monitoring_loop(),
            self._freshness_monitoring_loop(),
            self._update_processing_loop(),
            self._performance_monitoring_loop()
        ]
        
        await asyncio.gather(*monitoring_tasks, return_exceptions=True)
    
    async def stop_monitoring(self):
        """Stop monitoring"""
        logger.info("Stopping unified workflow monitoring")
        self._monitoring_enabled = False
    
    # === Event Management ===
    
    def subscribe(self, event_type: str, callback: Callable):
        """Subscribe to monitoring events"""
        if event_type not in self._event_subscribers:
            self._event_subscribers[event_type] = []
        self._event_subscribers[event_type].append(callback)
    
    async def emit_event(self, event: MonitoringEvent):
        """Emit monitoring event"""
        self._event_history.append(event)
        
        # Notify subscribers
        subscribers = self._event_subscribers.get(event.event_type.value, [])
        for callback in subscribers:
            try:
                await callback(event)
            except Exception as e:
                logger.error(f"Event subscriber failed: {e}")
        
        logger.info(f"Monitoring event: {event.event_type.value} - {event.component}")
    
    # === Change Detection ===
    
    async def _config_monitoring_loop(self):
        """Monitor configuration changes"""
        while self._monitoring_enabled:
            try:
                await self._check_configuration_changes()
                await asyncio.sleep(self.settings.monitoring.get("config_check_interval", 30))
            except Exception as e:
                logger.error(f"Config monitoring error: {e}")
                await asyncio.sleep(60)
    
    async def _check_configuration_changes(self):
        """Check for configuration changes"""
        # Compare current config with cached version
        current_config = self._get_current_config()
        
        for component, current_value in current_config.items():
            cached_value = self._config_cache.get(component)
            
            if cached_value is not None and cached_value != current_value:
                # Config change detected
                await self.record_change(
                    component=component,
                    old_value=cached_value,
                    new_value=current_value
                )
        
        # Update cache
        self._config_cache.update(current_config)
    
    def _get_current_config(self) -> Dict[str, Any]:
        """Get current configuration snapshot"""
        return {
            "enabled_providers": self.settings.get_enabled_providers(),
            "enabled_tools": self.settings.get_enabled_tools(),
            "workflow_config": self.settings.workflow.__dict__ if hasattr(self.settings.workflow, '__dict__') else {},
            "rag_config": self.settings.rag.__dict__ if hasattr(self.settings.rag, '__dict__') else {}
        }
    
    async def record_change(self, component: str, old_value: Any, new_value: Any, source: str = "system"):
        """Record configuration change"""
        event = MonitoringEvent(
            timestamp=datetime.now(),
            event_type=MonitoringEventType.CONFIG_CHANGE,
            component=component,
            severity="info",
            data={
                "old_value": old_value,
                "new_value": new_value,
                "source": source
            },
            source=source
        )
        
        await self.emit_event(event)
        
        # Trigger update if needed
        if self._should_trigger_update(component):
            await self.schedule_update(
                component=component,
                update_type="config_reload",
                config={"new_value": new_value}
            )
    
    def _should_trigger_update(self, component: str) -> bool:
        """Determine if change should trigger update"""
        critical_components = [
            "enabled_providers",
            "enabled_tools",
            "workflow_config"
        ]
        return component in critical_components
    
    # === Freshness Monitoring ===
    
    async def _freshness_monitoring_loop(self):
        """Monitor data freshness"""
        while self._monitoring_enabled:
            try:
                await self._check_data_freshness()
                await asyncio.sleep(self.settings.monitoring.get("freshness_check_interval", 300))
            except Exception as e:
                logger.error(f"Freshness monitoring error: {e}")
                await asyncio.sleep(600)
    
    async def _check_data_freshness(self):
        """Check all data sources for freshness"""
        stale_sources = []
        
        for source, threshold in self._staleness_thresholds.items():
            last_update = self._freshness_data.get(source)
            
            if not last_update:
                stale_sources.append((source, "never_updated"))
            elif datetime.now() - last_update > threshold:
                stale_sources.append((source, "stale"))
        
        for source, status in stale_sources:
            await self._handle_stale_data(source, status)
    
    async def _handle_stale_data(self, source: str, status: str):
        """Handle stale data detection"""
        event = MonitoringEvent(
            timestamp=datetime.now(),
            event_type=MonitoringEventType.DATA_STALENESS,
            component=source,
            severity="warning" if status == "stale" else "error",
            data={"status": status, "threshold": str(self._staleness_thresholds.get(source))},
            source="freshness_monitor"
        )
        
        await self.emit_event(event)
        
        # Schedule refresh update
        await self.schedule_update(
            component=source,
            update_type="data_refresh",
            config={"refresh_reason": status},
            priority=2 if status == "stale" else 1
        )
    
    async def update_freshness(self, source: str, timestamp: Optional[datetime] = None):
        """Update freshness timestamp"""
        self._freshness_data[source] = timestamp or datetime.now()
        logger.debug(f"Updated freshness for {source}")
    
    def is_fresh(self, source: str) -> bool:
        """Check if data source is fresh"""
        last_update = self._freshness_data.get(source)
        threshold = self._staleness_thresholds.get(source, timedelta(hours=1))
        
        if not last_update:
            return False
        
        return datetime.now() - last_update <= threshold
    
    # === Update Pipeline ===
    
    async def _update_processing_loop(self):
        """Process update queue"""
        while self._monitoring_enabled:
            try:
                await self._process_updates()
                await asyncio.sleep(self.settings.monitoring.get("update_interval", 60))
            except Exception as e:
                logger.error(f"Update processing error: {e}")
                await asyncio.sleep(120)
    
    async def schedule_update(
        self, 
        component: str, 
        update_type: str, 
        config: Dict[str, Any], 
        priority: int = 5
    ):
        """Schedule an update task"""
        update_task = UpdateTask(
            id=f"{component}_{datetime.now().isoformat()}",
            component=component,
            update_type=update_type,
            config=config,
            priority=priority,
            status=UpdateStatus.PENDING,
            scheduled_at=datetime.now()
        )
        
        self._update_queue.append(update_task)
        self._update_queue.sort(key=lambda x: x.priority)
        
        logger.info(f"Scheduled update: {update_type} for {component}")
    
    async def _process_updates(self):
        """Process pending updates"""
        if not self._update_queue:
            return
        
        # Process highest priority update
        update_task = self._update_queue.pop(0)
        
        try:
            update_task.status = UpdateStatus.IN_PROGRESS
            self._active_updates[update_task.id] = update_task
            
            success = await self._execute_update(update_task)
            
            if success:
                update_task.status = UpdateStatus.COMPLETED
                logger.info(f"Update completed: {update_task.id}")
            else:
                update_task.status = UpdateStatus.FAILED
                update_task.attempts += 1
                
                # Retry if not exceeded max attempts
                max_retries = self.settings.monitoring.get("max_update_retries", 3)
                if update_task.attempts < max_retries:
                    self._update_queue.append(update_task)
                    logger.warning(f"Update failed, retrying: {update_task.id}")
                else:
                    logger.error(f"Update failed permanently: {update_task.id}")
            
            self._active_updates.pop(update_task.id, None)
            
        except Exception as e:
            logger.error(f"Update execution error: {e}")
            update_task.status = UpdateStatus.FAILED
            self._active_updates.pop(update_task.id, None)
    
    async def _execute_update(self, update_task: UpdateTask) -> bool:
        """Execute specific update task"""
        try:
            if update_task.update_type == "config_reload":
                return await self._handle_config_reload(update_task)
            elif update_task.update_type == "data_refresh":
                return await self._handle_data_refresh(update_task)
            elif update_task.update_type == "component_restart":
                return await self._handle_component_restart(update_task)
            else:
                logger.warning(f"Unknown update type: {update_task.update_type}")
                return False
                
        except Exception as e:
            logger.error(f"Update execution failed: {e}")
            return False
    
    async def _handle_config_reload(self, update_task: UpdateTask) -> bool:
        """Handle configuration reload"""
        logger.info(f"Reloading config for {update_task.component}")
        
        # Implementation would reload actual configuration
        await asyncio.sleep(1)  # Simulate processing
        
        # Emit update event
        await self.emit_event(MonitoringEvent(
            timestamp=datetime.now(),
            event_type=MonitoringEventType.UPDATE_REQUIRED,
            component=update_task.component,
            severity="info",
            data={"update_type": "config_reload", "status": "completed"},
            source="update_pipeline"
        ))
        
        return True
    
    async def _handle_data_refresh(self, update_task: UpdateTask) -> bool:
        """Handle data refresh"""
        logger.info(f"Refreshing data for {update_task.component}")
        
        # Implementation would refresh actual data
        await asyncio.sleep(2)  # Simulate processing
        
        # Update freshness
        await self.update_freshness(update_task.component)
        
        return True
    
    async def _handle_component_restart(self, update_task: UpdateTask) -> bool:
        """Handle component restart"""
        logger.info(f"Restarting component: {update_task.component}")
        
        # Implementation would restart actual component
        await asyncio.sleep(3)  # Simulate processing
        
        return True
    
    # === Performance Monitoring ===
    
    async def _performance_monitoring_loop(self):
        """Monitor performance metrics"""
        while self._monitoring_enabled:
            try:
                await self._check_performance_metrics()
                await asyncio.sleep(self.settings.monitoring.get("performance_check_interval", 120))
            except Exception as e:
                logger.error(f"Performance monitoring error: {e}")
                await asyncio.sleep(300)
    
    async def _check_performance_metrics(self):
        """Check performance metrics"""
        # Monitor queue sizes
        if len(self._update_queue) > 10:
            await self.emit_event(MonitoringEvent(
                timestamp=datetime.now(),
                event_type=MonitoringEventType.PERFORMANCE_ISSUE,
                component="update_queue",
                severity="warning",
                data={"queue_size": len(self._update_queue), "threshold": 10},
                source="performance_monitor"
            ))
        
        # Monitor active updates
        if len(self._active_updates) > 5:
            await self.emit_event(MonitoringEvent(
                timestamp=datetime.now(),
                event_type=MonitoringEventType.PERFORMANCE_ISSUE,
                component="active_updates",
                severity="warning", 
                data={"active_count": len(self._active_updates), "threshold": 5},
                source="performance_monitor"
            ))
    
    # === Status Methods ===
    
    def get_monitoring_status(self) -> Dict[str, Any]:
        """Get overall monitoring status"""
        recent_events = [
            event for event in self._event_history 
            if event.timestamp > datetime.now() - timedelta(hours=1)
        ]
        
        return {
            "monitoring_enabled": self._monitoring_enabled,
            "recent_events_count": len(recent_events),
            "update_queue_size": len(self._update_queue),
            "active_updates_count": len(self._active_updates),
            "freshness_status": {
                source: self.is_fresh(source) 
                for source in self._staleness_thresholds.keys()
            },
            "last_check": datetime.now()
        }
    
    def get_recent_events(self, hours: int = 24) -> List[MonitoringEvent]:
        """Get recent monitoring events"""
        cutoff = datetime.now() - timedelta(hours=hours)
        return [event for event in self._event_history if event.timestamp > cutoff]
    
    def get_update_status(self, update_id: str) -> Optional[UpdateTask]:
        """Get status of specific update"""
        return self._active_updates.get(update_id)

# Singleton instance
unified_monitor = UnifiedWorkflowMonitor() 