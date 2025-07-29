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
    """JSON formatter for structured logging""" 
    
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
        
        if hasattr(record, 'user_id'):
            log_entry['user_id'] = record.user_id
        if hasattr(record, 'request_id'):
            log_entry['request_id'] = record.request_id
        if hasattr(record, 'execution_time'):
            log_entry['execution_time'] = record.execution_time
        
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
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        formatted_message = (
            f"{color}[{timestamp}] {record.levelname:8s}{reset} "
            f"{record.name:20s} | {record.getMessage()}"
        )
        
        return formatted_message

def setup_logging() -> None:
    """Setup logging configuration"""
    
    import os
    log_base = os.getenv("LOG_DIR", "./logs")
    log_dir = Path(log_base)
    log_dir.mkdir(parents=True, exist_ok=True)
   
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG if settings.DEBUG else logging.INFO)
    
    root_logger.handlers.clear()
    
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.DEBUG if settings.DEBUG else logging.INFO)
    
    if settings.DEBUG:
        console_formatter = ColoredFormatter()
    else:
        console_formatter = JsonFormatter()
    
    console_handler.setFormatter(console_formatter)
    root_logger.addHandler(console_handler)
    
    file_handler = logging.handlers.RotatingFileHandler(
        filename=log_dir / "app.log",
        maxBytes=10 * 1024 * 1024,  # 10MB
        backupCount=5,
        encoding='utf-8'
    )
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(JsonFormatter())
    root_logger.addHandler(file_handler)
    
    error_handler = logging.handlers.RotatingFileHandler(
        filename=log_dir / "error.log",
        maxBytes=10 * 1024 * 1024,  # 10MB
        backupCount=5,
        encoding='utf-8'
    )
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(JsonFormatter())
    root_logger.addHandler(error_handler)
    
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
    access_logger.propagate = False
    logging.getLogger("uvicorn").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("sentence_transformers").setLevel(logging.WARNING)
    
    if not settings.DEBUG:
        logging.getLogger("asyncio").setLevel(logging.WARNING)
        logging.getLogger("multipart").setLevel(logging.WARNING)

def get_logger(name: str) -> logging.Logger:
    """Get logger instance with specific name"""
    
    if not logging.getLogger().handlers:
        setup_logging()
    
    return logging.getLogger(name)

class LoggerMixin:
    """Mixin class to add logging to classes"""
    
    @property
    def logger(self) -> logging.Logger:
        """Get logger for current class"""
        return get_logger(self.__class__.__name__)

class RequestLoggerAdapter(logging.LoggerAdapter):
    """Logger adapter to add request context"""
    
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
    """Get logger with request context"""
    logger = get_logger(name)
    return RequestLoggerAdapter(logger, request_id, user_id)

def log_performance(logger_name: Optional[str] = None):
    """Decorator to log performance of functions""" 
    
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

if not logging.getLogger().handlers:
    setup_logging()