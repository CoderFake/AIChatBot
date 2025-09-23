"""
Database configuration with SQLAlchemy async support
Multi-tenant database setup with connection pooling
"""
import asyncio
from typing import AsyncGenerator, Optional
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import event, text
from sqlalchemy.exc import DisconnectionError, OperationalError
from sqlalchemy.pool import NullPool

from config.settings import get_settings
from utils.logging import get_logger
from models.database.base import Base

logger = get_logger(__name__)
settings = get_settings()

class DatabaseManager:
    """Async database manager with proper connection handling and cancellation support"""
    
    def __init__(self):
        self.engine = None
        self.async_session_factory = None
        self._initialized = False
        self._loop: Optional[asyncio.AbstractEventLoop] = None
    
    async def initialize(self):
        """Initialize database engine and session factory"""
        if self._initialized:
            return
        
        try:
            try:
                self._loop = asyncio.get_running_loop()
            except RuntimeError:
                self._loop = asyncio.get_event_loop()
            database_url = settings.database_url.replace("postgresql://", "postgresql+asyncpg://")
            
            self.engine = create_async_engine(
                database_url,
                pool_pre_ping=True,
                echo=settings.DEBUG,
                future=True,
                pool_size=5,
                max_overflow=0, 
                pool_recycle=3600,
                pool_timeout=30,
                pool_use_lifo=True,
                connect_args={
                    "server_settings": {
                        "application_name": "ai_chatbot_api",
                        "jit": "off",
                        "statement_timeout": "30000",
                        "idle_in_transaction_session_timeout": "30000"
                    },
                    "command_timeout": 30
                }
            )
            
            @event.listens_for(self.engine.sync_engine, "connect")
            def set_postgres_settings(dbapi_connection, connection_record):
                try:
                    cursor = dbapi_connection.cursor()
                    try:
                        cursor.execute("SET TIME ZONE 'UTC'")
                        cursor.execute("SET statement_timeout = '30s'")
                        cursor.execute("SET idle_in_transaction_session_timeout = '60s'")
                    finally:
                        try:
                            cursor.close()
                        except Exception:
                            pass
                except Exception as e:
                    logger.warning(f"Failed to set connection settings: {e}")

            @event.listens_for(self.engine.sync_engine, "checkout")
            def receive_checkout(dbapi_connection, connection_record, connection_proxy):
                """Handle connection checkout"""
                logger.debug("Connection checked out from pool")

            @event.listens_for(self.engine.sync_engine, "checkin")
            def receive_checkin(dbapi_connection, connection_record):
                """Handle connection checkin"""
                logger.debug("Connection returned to pool")

            @event.listens_for(self.engine.sync_engine, "invalidate")
            def receive_invalidate(dbapi_connection, connection_record, exception):
                """Handle connection invalidation"""
                logger.warning(f"Connection invalidated: {exception}")
            
            self.async_session_factory = async_sessionmaker(
                bind=self.engine,
                class_=AsyncSession,
                expire_on_commit=False,
                autoflush=False,
                autocommit=False
            )
            
            await self.test_connection()
            
            self._initialized = True
            logger.info("Database initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize database: {e}")
            raise
    
    async def test_connection(self) -> bool:
        """Test database connection"""
        try:
            async with self.engine.begin() as conn:
                await conn.execute(text("SELECT 1"))
            return True
        except Exception as e:
            logger.error(f"Database connection test failed: {e}")
            return False
    
    async def create_tables(self):
        """Create all database tables"""
        try:
            async with self.engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            logger.info("Database tables created successfully")
        except Exception as e:
            logger.error(f"Failed to create tables: {e}")
            raise
    
    async def close(self):
        """Close database connections properly"""
        if self.engine:
            try:
                await asyncio.wait_for(self.engine.dispose(), timeout=30.0)
                logger.info("Database connections closed")
            except asyncio.TimeoutError:
                logger.warning("Database close operation timed out")
            except Exception as e:
                logger.error(f"Error closing database: {e}")
            finally:
                self.engine = None
                self._initialized = False

db_manager = DatabaseManager()

async def init_db():
    """Initialize database on application startup"""
    await db_manager.initialize()
    await db_manager.create_tables()

async def close_db():
    """Close database on application shutdown"""
    await db_manager.close()

@asynccontextmanager
async def get_db_context():
    """Context manager for database session with proper cancellation handling"""
    try:
        current_loop = asyncio.get_running_loop()
    except RuntimeError:
        current_loop = asyncio.get_event_loop()

    if not db_manager._initialized:
        await db_manager.initialize()
    elif db_manager._loop is not None and current_loop is not db_manager._loop:
        try:
            await db_manager.close()
        except Exception:
            pass
        await db_manager.initialize()
    
    session = None
    try:
        session = db_manager.async_session_factory()
        yield session
        
        if session.in_transaction():
            await session.commit()
            
    except asyncio.CancelledError:
        logger.warning("Database session cancelled")
        if session and session.in_transaction():
            try:
                await session.rollback()
            except Exception as e:
                logger.error(f"Error during rollback on cancellation: {e}")
        
        # Invalidate connection on cancellation to prevent leaks
        if session:
            try:
                connection = await session.get_bind()
                if hasattr(connection, 'invalidate'):
                    await connection.invalidate()
            except Exception as e:
                logger.error(f"Error invalidating connection: {e}")
        raise
        
    except (DisconnectionError, OperationalError) as e:
        logger.error(f"Database connection error: {e}")
        if session and session.in_transaction():
            try:
                await session.rollback()
            except Exception:
                pass
        
        if session:
            try:
                connection = await session.get_bind()
                if hasattr(connection, 'invalidate'):
                    await connection.invalidate()
            except Exception as e:
                logger.debug(f"Error invalidating connection: {e}")
        raise
        
    except Exception as e:
        logger.error(f"Database session error: {e}")
        if session and session.in_transaction():
            try:
                await session.rollback()
            except Exception as rollback_error:
                logger.error(f"Error during rollback: {rollback_error}")
        raise
        
    finally:
        if session:
            try:
                await asyncio.wait_for(session.close(), timeout=10.0)
            except asyncio.TimeoutError:
                logger.warning("Session close operation timed out")
            except Exception as close_error:
                logger.error(f"Error closing session: {close_error}")

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency for getting database session"""
    async with get_db_context() as session:
        yield session

def get_db_session() -> AsyncSession:
    """Get synchronous database session for non-async contexts"""
    if not db_manager._initialized:
        raise RuntimeError("Database not initialized")
    return db_manager.async_session_factory()

async def execute_db_operation(operation_func):
    """Execute database operation with proper error handling"""
    async with get_db_context() as session:
        return await operation_func(session)


async def test_connection() -> bool:
    """Test database connection health"""
    return await db_manager.test_connection()

class DatabaseHealthCheck:
    """Database health check utilities"""
    
    @staticmethod
    async def check_connectivity() -> dict:
        """Comprehensive database health check"""
        try:
            is_connected = await test_connection()
            
            if is_connected:
                async with get_db_context() as session:
                    result = await session.execute(text("SELECT version()"))
                    version = result.scalar()
                    
                    pool = db_manager.engine.pool
                    
                    return {
                        "status": "healthy",
                        "connected": True,
                        "database_version": version,
                        "pool_size": pool.size(),
                        "checked_out": pool.checkedout(),
                        "overflow": pool.overflow(),
                        "checked_in": pool.checkedin()
                    }
            else:
                return {
                    "status": "unhealthy",
                    "connected": False,
                    "error": "Connection failed"
                }
                
        except Exception as e:
            logger.error(f"Database health check failed: {e}")
            return {
                "status": "error",
                "connected": False,
                "error": str(e)
            }