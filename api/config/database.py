"""
Database configuration with SQLAlchemy async support
Multi-tenant database setup with connection pooling
"""
import asyncio
from typing import AsyncGenerator, Optional
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.pool import QueuePool
from sqlalchemy import event, text
from sqlalchemy.exc import DisconnectionError, InvalidRequestError

from config.settings import get_settings
from utils.logging import get_logger
from models.database.base import Base

logger = get_logger(__name__)
settings = get_settings()

class DatabaseManager:
    """Async database manager with connection pooling and health checks"""
    
    def __init__(self):
        self.engine = None
        self.async_session_factory = None
        self._initialized = False
    
    async def initialize(self):
        """Initialize database engine and session factory"""
        if self._initialized:
            return
        
        try:
            database_url = settings.database_url.replace("postgresql://", "postgresql+asyncpg://")
            
            self.engine = create_async_engine(
                database_url,
                poolclass=QueuePool,
                pool_size=20,
                max_overflow=30,
                pool_timeout=30,
                pool_recycle=1800,
                pool_pre_ping=True,
                echo=settings.DEBUG,
                future=True
            )
            
            @event.listens_for(self.engine.sync_engine, "connect")
            def set_sqlite_pragma(dbapi_connection, connection_record):
                if "postgresql" in str(dbapi_connection):
                    with dbapi_connection.cursor() as cursor:
                        cursor.execute("SET timezone = 'UTC'")
            
            self.async_session_factory = async_sessionmaker(
                bind=self.engine,
                class_=AsyncSession,
                expire_on_commit=False,
                autoflush=False,
                autocommit=False
            )
            
            # Test connection
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
        """Close database connections"""
        if self.engine:
            await self.engine.dispose()
            logger.info("Database connections closed")

db_manager = DatabaseManager()

async def init_db():
    """Initialize database on application startup"""
    await db_manager.initialize()
    await db_manager.create_tables()

async def close_db():
    """Close database on application shutdown"""
    await db_manager.close()

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency for getting database session"""
    if not db_manager._initialized:
        await db_manager.initialize()
    
    async with db_manager.async_session_factory() as session:
        try:
            yield session
        except Exception as e:
            await session.rollback()
            logger.error(f"Database session error: {e}")
            raise
        finally:
            await session.close()

def get_db_session() -> AsyncSession:
    """Get synchronous database session for non-async contexts"""
    if not db_manager._initialized:
        raise RuntimeError("Database not initialized")
    return db_manager.async_session_factory()

@asynccontextmanager
async def get_db_context():
    """Context manager for database session"""
    async with get_db() as session:
        yield session

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