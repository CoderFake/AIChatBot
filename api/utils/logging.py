import logging
import logging.handlers
import sys
import os
from datetime import datetime
from typing import Optional
import json
from pathlib import Path

from config.settings import get_settings

settings = get_settings()

class JsonFormatter(logging.Formatter):
    """JSON formatter cho structured logging"""
    
    def format(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        
        # Thêm extra fields nếu có
        if hasattr(record, 'user_id'):
            log_entry['user_id'] = record.user_id
        if hasattr(record, 'request_id'):
            log_entry['request_id'] = record.request_id
        if hasattr(record, 'execution_time'):
            log_entry['execution_time'] = record.execution_time
        
        # Thêm exception info nếu có
        if record.exc_info:
            log_entry['exception'] = self.formatException(record.exc_info)
        
        return json.dumps(log_entry, ensure_ascii=False)

class ColoredFormatter(logging.Formatter):
    """Colored formatter cho console output"""
    
    COLORS = {
        'DEBUG': '\033[36m',     # Cyan
        'INFO': '\033[32m',      # Green
        'WARNING': '\033[33m',   # Yellow
        'ERROR': '\033[31m',     # Red
        'CRITICAL': '\033[35m',  # Magenta
        'RESET': '\033[0m'       # Reset
    }
    
    def format(self, record: logging.LogRecord) -> str:
        if not settings.DEBUG:
            return super().format(record)
        
        color = self.COLORS.get(record.levelname, self.COLORS['RESET'])
        reset = self.COLORS['RESET']
        
        # Format timestamp
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        # Format message
        formatted_message = (
            f"{color}[{timestamp}] {record.levelname:8s}{reset} "
            f"{record.name:20s} | {record.getMessage()}"
        )
        
        return formatted_message

def setup_logging() -> None:
    """Setup logging configuration"""
    
    # Tạo thư mục logs nếu chưa có
    log_dir = Path("/app/logs")
    log_dir.mkdir(exist_ok=True)
    
    # Root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG if settings.DEBUG else logging.INFO)
    
    # Clear existing handlers
    root_logger.handlers.clear()
    
    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.DEBUG if settings.DEBUG else logging.INFO)
    
    if settings.DEBUG:
        console_formatter = ColoredFormatter()
    else:
        console_formatter = JsonFormatter()
    
    console_handler.setFormatter(console_formatter)
    root_logger.addHandler(console_handler)
    
    # File handler cho general logs
    file_handler = logging.handlers.RotatingFileHandler(
        filename=log_dir / "app.log",
        maxBytes=10 * 1024 * 1024,  # 10MB
        backupCount=5,
        encoding='utf-8'
    )
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(JsonFormatter())
    root_logger.addHandler(file_handler)
    
    # Error file handler
    error_handler = logging.handlers.RotatingFileHandler(
        filename=log_dir / "error.log",
        maxBytes=10 * 1024 * 1024,  # 10MB
        backupCount=5,
        encoding='utf-8'
    )
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(JsonFormatter())
    root_logger.addHandler(error_handler)
    
    # Access log handler
    access_logger = logging.getLogger("access")
    access_handler = logging.handlers.RotatingFileHandler(
        filename=log_dir / "access.log",
        maxBytes=10 * 1024 * 1024,  # 10MB
        backupCount=5,
        encoding='utf-8'
    )
    access_handler.setFormatter(JsonFormatter())
    access_logger.addHandler(access_handler)
    access_logger.setLevel(logging.INFO)
    
    # Disable propagation để tránh duplicate logs
    access_logger.propagate = False
    
    # Third-party library loggers
    logging.getLogger("uvicorn").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("sentence_transformers").setLevel(logging.WARNING)
    
    if not settings.DEBUG:
        logging.getLogger("asyncio").setLevel(logging.WARNING)
        logging.getLogger("multipart").setLevel(logging.WARNING)

def get_logger(name: str) -> logging.Logger:
    """Get logger instance với tên cụ thể"""
    
    # Setup logging nếu chưa được setup
    if not logging.getLogger().handlers:
        setup_logging()
    
    return logging.getLogger(name)

class LoggerMixin:
    """Mixin class để thêm logging vào classes"""
    
    @property
    def logger(self) -> logging.Logger:
        """Get logger cho class hiện tại"""
        return get_logger(self.__class__.__name__)

class RequestLoggerAdapter(logging.LoggerAdapter):
    """Logger adapter để thêm request context"""
    
    def __init__(self, logger: logging.Logger, request_id: str, user_id: Optional[str] = None):
        super().__init__(logger, {})
        self.request_id = request_id
        self.user_id = user_id
    
    def process(self, msg, kwargs):
        kwargs['extra'] = kwargs.get('extra', {})
        kwargs['extra']['request_id'] = self.request_id
        if self.user_id:
            kwargs['extra']['user_id'] = self.user_id
        return msg, kwargs

def get_request_logger(
    name: str, 
    request_id: str, 
    user_id: Optional[str] = None
) -> RequestLoggerAdapter:
    """Get logger với request context"""
    logger = get_logger(name)
    return RequestLoggerAdapter(logger, request_id, user_id)

# Performance logging decorator
def log_performance(logger_name: Optional[str] = None):
    """Decorator để log performance của functions"""
    
    def decorator(func):
        import functools
        import time
        import asyncio
        
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            logger = get_logger(logger_name or func.__module__)
            start_time = time.time()
            
            try:
                result = await func(*args, **kwargs)
                execution_time = time.time() - start_time
                
                logger.info(
                    f"Function {func.__name__} completed",
                    extra={"execution_time": execution_time}
                )
                
                return result
            except Exception as e:
                execution_time = time.time() - start_time
                logger.error(
                    f"Function {func.__name__} failed: {str(e)}",
                    extra={"execution_time": execution_time},
                    exc_info=True
                )
                raise
        
        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            logger = get_logger(logger_name or func.__module__)
            start_time = time.time()
            
            try:
                result = func(*args, **kwargs)
                execution_time = time.time() - start_time
                
                logger.info(
                    f"Function {func.__name__} completed",
                    extra={"execution_time": execution_time}
                )
                
                return result
            except Exception as e:
                execution_time = time.time() - start_time
                logger.error(
                    f"Function {func.__name__} failed: {str(e)}",
                    extra={"execution_time": execution_time},
                    exc_info=True
                )
                raise
        
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator

# Initialize logging when module is imported
if not logging.getLogger().handlers:
    setup_logging()