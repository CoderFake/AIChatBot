from typing import Any, Dict, Optional
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
import traceback

from utils.logging import get_logger

logger = get_logger(__name__)

class BaseAPIException(Exception):
    """Base exception class cho API"""
    
    def __init__(
        self,
        message: str,
        status_code: int = 500,
        error_code: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        self.message = message
        self.status_code = status_code
        self.error_code = error_code or self.__class__.__name__
        self.details = details or {}
        super().__init__(self.message)

class ValidationError(BaseAPIException):
    """Validation error exception"""
    
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=message,
            status_code=400,
            error_code="VALIDATION_ERROR",
            details=details
        )

class AuthenticationError(BaseAPIException):
    """Authentication error exception"""
    
    def __init__(self, message: str = "Authentication required"):
        super().__init__(
            message=message,
            status_code=401,
            error_code="AUTHENTICATION_ERROR"
        )

class AuthorizationError(BaseAPIException):
    """Authorization error exception"""
    
    def __init__(self, message: str = "Insufficient permissions"):
        super().__init__(
            message=message,
            status_code=403,
            error_code="AUTHORIZATION_ERROR"
        )

class NotFoundError(BaseAPIException):
    """Not found error exception"""
    
    def __init__(self, message: str = "Resource not found"):
        super().__init__(
            message=message,
            status_code=404,
            error_code="NOT_FOUND_ERROR"
        )

class ConflictError(BaseAPIException):
    """Conflict error exception"""
    
    def __init__(self, message: str = "Resource conflict"):
        super().__init__(
            message=message,
            status_code=409,
            error_code="CONFLICT_ERROR"
        )

class RateLimitError(BaseAPIException):
    """Rate limit error exception"""
    
    def __init__(self, message: str = "Rate limit exceeded"):
        super().__init__(
            message=message,
            status_code=429,
            error_code="RATE_LIMIT_ERROR"
        )

class ServiceError(BaseAPIException):
    """Internal service error exception"""
    
    def __init__(self, message: str = "Internal service error"):
        super().__init__(
            message=message,
            status_code=500,
            error_code="SERVICE_ERROR"
        )

class ExternalServiceError(BaseAPIException):
    """External service error exception"""
    
    def __init__(self, message: str = "External service error", service_name: str = "unknown"):
        super().__init__(
            message=message,
            status_code=502,
            error_code="EXTERNAL_SERVICE_ERROR",
            details={"service": service_name}
        )

class LLMProviderError(BaseAPIException):
    """LLM provider error exception"""
    
    def __init__(self, message: str = "LLM provider error", provider: str = "unknown"):
        super().__init__(
            message=message,
            status_code=502,
            error_code="LLM_PROVIDER_ERROR",
            details={"provider": provider}
        )

class VectorDatabaseError(BaseAPIException):
    """Vector database error exception"""
    
    def __init__(self, message: str = "Vector database error"):
        super().__init__(
            message=message,
            status_code=503,
            error_code="VECTOR_DATABASE_ERROR"
        )

class DocumentProcessingError(BaseAPIException):
    """Document processing error exception"""
    
    def __init__(self, message: str = "Document processing error", document_id: Optional[str] = None):
        super().__init__(
            message=message,
            status_code=422,
            error_code="DOCUMENT_PROCESSING_ERROR",
            details={"document_id": document_id} if document_id else {}
        )

class WorkflowError(BaseAPIException):
    """Workflow execution error exception"""
    
    def __init__(self, message: str = "Workflow execution error", workflow_id: Optional[str] = None):
        super().__init__(
            message=message,
            status_code=500,
            error_code="WORKFLOW_ERROR",
            details={"workflow_id": workflow_id} if workflow_id else {}
        )

class LangGraphError(BaseAPIException):
    """LangGraph execution error exception"""
    
    def __init__(self, message: str = "LangGraph execution error", node: Optional[str] = None):
        super().__init__(
            message=message,
            status_code=500,
            error_code="LANGGRAPH_ERROR",
            details={"node": node} if node else {}
        )

async def base_api_exception_handler(request: Request, exc: BaseAPIException) -> JSONResponse:
    """Handler cho BaseAPIException và subclasses"""
    
    logger.error(
        f"API Exception: {exc.error_code} - {exc.message}",
        extra={
            "error_code": exc.error_code,
            "status_code": exc.status_code,
            "details": exc.details,
            "path": request.url.path,
            "method": request.method,
        }
    )
    
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "code": exc.error_code,
                "message": exc.message,
                "details": exc.details
            },
            "path": request.url.path,
            "method": request.method
        }
    )

async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    """Handler cho HTTPException"""
    
    logger.warning(
        f"HTTP Exception: {exc.status_code} - {exc.detail}",
        extra={
            "status_code": exc.status_code,
            "path": request.url.path,
            "method": request.method,
        }
    )
    
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "code": "HTTP_ERROR",
                "message": exc.detail,
                "details": {}
            },
            "path": request.url.path,
            "method": request.method
        }
    )

async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """Handler cho RequestValidationError"""
    
    logger.warning(
        f"Validation Error: {exc.errors()}",
        extra={
            "errors": exc.errors(),
            "path": request.url.path,
            "method": request.method,
        }
    )
    
    return JSONResponse(
        status_code=422,
        content={
            "error": {
                "code": "VALIDATION_ERROR",
                "message": "Request validation failed",
                "details": {
                    "errors": exc.errors(),
                    "body": str(exc.body) if hasattr(exc, 'body') else None
                }
            },
            "path": request.url.path,
            "method": request.method
        }
    )

async def general_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Handler cho tất cả exceptions khác"""
    
    logger.error(
        f"Unhandled Exception: {str(exc)}",
        extra={
            "exception_type": type(exc).__name__,
            "traceback": traceback.format_exc(),
            "path": request.url.path,
            "method": request.method,
        }
    )
    
    return JSONResponse(
        status_code=500,
        content={
            "error": {
                "code": "INTERNAL_ERROR",
                "message": "An internal error occurred",
                "details": {
                    "type": type(exc).__name__
                }
            },
            "path": request.url.path,
            "method": request.method
        }
    )

def setup_exception_handlers(app: FastAPI) -> None:
    """Setup tất cả exception handlers cho FastAPI app"""
    
    app.add_exception_handler(BaseAPIException, base_api_exception_handler)
    app.add_exception_handler(HTTPException, http_exception_handler)
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(Exception, general_exception_handler)
    
    logger.info("Exception handlers registered successfully")