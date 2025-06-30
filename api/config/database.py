from typing import AsyncGenerator, Optional
from sqlalchemy import create_engine, event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import NullPool, QueuePool
import asyncio
from contextlib import asynccontextmanager
import asyncpg
from asyncpg import Pool
from sqlalchemy import MetaData

from config.settings import get_settings
from utils.logging import get_logger

logger = get_logger(__name__)
settings = get_settings()


class Base(declarative_base()):
    metadata = MetaData(
        naming_convention={
            "ix": "ix_%(column_0_label)s",
            "uq": "uq_%(table_name)s_%(column_0_name)s",
            "ck": "ck_%(table_name)s_%(constraint_name)s",
            "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
            "pk": "pk_%(table_name)s"
        }
    )

# Global variables
engine: Optional[object] = None
async_session_factory: Optional[async_sessionmaker] = None
pg_pool: Optional[Pool] = None

class DatabaseManager:
    """
    Quản lý kết nối database với hỗ trợ cả sync và async operations
    """
    
    def __init__(self):
        self._async_engine = None
        self._sync_engine = None
        self._async_session_factory = None
        self._sync_session_factory = None
        self._initialized = False
    
    async def initialize(self):
        """
        Khởi tạo database engines và session factories
        """
        if self._initialized:
            return
        
        try:
            await self._create_async_engine()
            self._create_sync_engine()
            self._create_session_factories()
            await self._setup_event_listeners()
            
            self._initialized = True
            logger.info("Database manager initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize database manager: {str(e)}")
            raise
    
    async def _create_async_engine(self):
        """
        Tạo async SQLAlchemy engine
        """
        sqlalchemy_config = settings.get_sqlalchemy_config()
        
        pool_config = {
            "poolclass": QueuePool,
            "pool_size": sqlalchemy_config["pool_size"],
            "max_overflow": sqlalchemy_config["max_overflow"],
            "pool_timeout": sqlalchemy_config["pool_timeout"],
            "pool_recycle": sqlalchemy_config["pool_recycle"],
            "pool_pre_ping": sqlalchemy_config["pool_pre_ping"]
        }
        
        echo_config = {
            "echo": sqlalchemy_config["echo"] and not settings.is_production,
            "echo_pool": sqlalchemy_config["echo_pool"] and not settings.is_production
        }
        
        self._async_engine = create_async_engine(
            settings.DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://"),
            echo=settings.DEBUG,
            pool_size=10,
            max_overflow=20,
            pool_pre_ping=True,
            pool_recycle=3600,
        )
        
        logger.info(f"Async database engine created: {settings.DATABASE_HOST}:{settings.DATABASE_PORT}")
    
    def _create_sync_engine(self):
        """
        Tạo sync SQLAlchemy engine cho migrations và admin tasks
        """
        sqlalchemy_config = settings.get_sqlalchemy_config()
        
        pool_config = {
            "poolclass": QueuePool,
            "pool_size": sqlalchemy_config["pool_size"] // 2, 
            "max_overflow": sqlalchemy_config["max_overflow"] // 2,
            "pool_timeout": sqlalchemy_config["pool_timeout"],
            "pool_recycle": sqlalchemy_config["pool_recycle"],
            "pool_pre_ping": sqlalchemy_config["pool_pre_ping"]
        }
        
        echo_config = {
            "echo": sqlalchemy_config["echo"] and not settings.is_production,
            "echo_pool": sqlalchemy_config["echo_pool"] and not settings.is_production
        }
        
        self._sync_engine = create_engine(
            settings.database_url,
            **pool_config,
            **echo_config,
            future=True
        )
        
        logger.info(f"Sync database engine created: {settings.DATABASE_HOST}:{settings.DATABASE_PORT}")
    
    def _create_session_factories(self):
        """
        Tạo session factories cho cả async và sync
        """
        self._async_session_factory = async_sessionmaker(
            bind=self._async_engine,
            class_=AsyncSession,
            expire_on_commit=False,
            autoflush=True,
            autocommit=False
        )
        
        self._sync_session_factory = sessionmaker(
            bind=self._sync_engine,
            class_=Session,
            expire_on_commit=False,
            autoflush=True,
            autocommit=False
        )
        
        logger.info("Database session factories created")
    
    async def _setup_event_listeners(self):
        """
        Setup SQLAlchemy event listeners cho monitoring và logging
        """
        if settings.PERFORMANCE_MONITORING:
            @event.listens_for(self._async_engine.sync_engine, "connect")
            def on_connect(dbapi_connection, connection_record):
                logger.debug("Database connection established")
            
            @event.listens_for(self._async_engine.sync_engine, "close")
            def on_close(dbapi_connection, connection_record):
                logger.debug("Database connection closed")
            
            @event.listens_for(self._async_engine.sync_engine, "before_cursor_execute")
            def before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
                context._query_start_time = asyncio.get_event_loop().time()
            
            @event.listens_for(self._async_engine.sync_engine, "after_cursor_execute")
            def after_cursor_execute(conn, cursor, statement, parameters, context, executemany):
                total = asyncio.get_event_loop().time() - context._query_start_time
                if total > 1.0:
                    logger.warning(f"Slow query detected: {total:.2f}s - {statement[:100]}...")
    
    async def get_async_session(self) -> AsyncGenerator[AsyncSession, None]:
        """
        Async context manager để lấy database session
        """
        if not self._initialized:
            await self.initialize()
        
        async with self._async_session_factory() as session:
            try:
                yield session
            except Exception as e:
                await session.rollback()
                logger.error(f"Database session error: {str(e)}")
                raise
            finally:
                await session.close()
    
    def get_sync_session(self):
        """
        Sync context manager để lấy database session
        """
        if not self._initialized:
            raise RuntimeError("Database manager not initialized. Call initialize() first.")
        
        return self._sync_session_factory()
    
    @asynccontextmanager
    async def transaction(self):
        """
        Async transaction context manager
        """
        async with self.get_async_session() as session:
            async with session.begin():
                yield session
    
    async def create_all_tables(self):
        """
        Tạo tất cả tables trong database
        """
        if not self._initialized:
            await self.initialize()
        
        async with self._async_engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        
        logger.info("All database tables created")
    
    async def drop_all_tables(self):
        """
        Xóa tất cả tables trong database
        """
        if not self._initialized:
            await self.initialize()
        
        async with self._async_engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
        
        logger.warning("All database tables dropped")
    
    async def check_connection(self) -> bool:
        """
        Kiểm tra kết nối database
        """
        try:
            async with self.get_async_session() as session:
                await session.execute("SELECT 1")
                return True
        except Exception as e:
            logger.error(f"Database connection check failed: {str(e)}")
            return False
    
    async def get_connection_info(self) -> dict:
        """
        Lấy thông tin kết nối database
        """
        if not self._async_engine:
            return {"status": "not_initialized"}
        
        pool = self._async_engine.pool
        return {
            "status": "connected",
            "host": settings.DATABASE_HOST,
            "port": settings.DATABASE_PORT,
            "database": settings.DATABASE_NAME,
            "pool_size": pool.size(),
            "checked_in_connections": pool.checkedin(),
            "checked_out_connections": pool.checkedout(),
            "overflow_connections": pool.overflow(),
            "invalid_connections": pool.invalidated()
        }
    
    async def close(self):
        """
        Đóng tất cả database connections
        """
        if self._async_engine:
            await self._async_engine.dispose()
            logger.info("Async database engine closed")
        
        if self._sync_engine:
            self._sync_engine.dispose()
            logger.info("Sync database engine closed")
        
        self._initialized = False


db_manager = DatabaseManager()


async def get_async_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Dependency function để inject async database session vào FastAPI endpoints
    """
    async with db_manager.get_async_session() as session:
        yield session


def get_sync_db() -> Session:
    """
    Function để lấy sync database session
    """
    return db_manager.get_sync_session()


async def init_database():
    """
    Khởi tạo database khi application start
    """
    try:
        await db_manager.initialize()
        
        if await db_manager.check_connection():
            logger.info("Database connection established successfully")
        else:
            raise Exception("Database connection check failed")
        
        if settings.is_development:
            await db_manager.create_all_tables()
        
    except Exception as e:
        logger.error(f"Database initialization failed: {str(e)}")
        raise


async def close_database():
    """
    Đóng database connections khi application shutdown
    """
    await db_manager.close()
    logger.info("Database connections closed")


class DatabaseHealthCheck:
    """
    Health check cho database connection
    """
    
    @staticmethod
    async def check() -> dict:
        """
        Kiểm tra health của database
        """
        try:
            connection_info = await db_manager.get_connection_info()
            is_healthy = await db_manager.check_connection()
            
            return {
                "service": "database",
                "status": "healthy" if is_healthy else "unhealthy",
                "details": connection_info,
                "timestamp": settings.TIMEZONE
            }
        
        except Exception as e:
            return {
                "service": "database",
                "status": "unhealthy",
                "error": str(e),
                "timestamp": settings.TIMEZONE
            }

async def init_db():
    """Initialize database connections"""
    global engine, async_session_factory, pg_pool
    
    try:
        engine = create_async_engine(
            settings.DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://"),
            echo=settings.DEBUG,
            pool_size=10,
            max_overflow=20,
            pool_pre_ping=True,
            pool_recycle=3600,
        )

        async_session_factory = async_sessionmaker(
            engine,
            class_=AsyncSession,
            expire_on_commit=False
        )
        
        pg_pool = await asyncpg.create_pool(
            settings.DATABASE_URL,
            min_size=5,
            max_size=20,
            command_timeout=60,
            server_settings={
                'jit': 'off'
            }
        )
        
        logger.info("Database connections initialized successfully")
        
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
        raise

async def close_db():
    """Close database connections"""
    global engine, pg_pool
    
    try:
        if engine:
            await engine.dispose()
            logger.info("SQLAlchemy engine closed")
        
        if pg_pool:
            await pg_pool.close()
            logger.info("AsyncPG pool closed")
            
    except Exception as e:
        logger.error(f"Error closing database connections: {e}")

async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Get database session"""
    if not async_session_factory:
        raise RuntimeError("Database not initialized")
    
    async with async_session_factory() as session:
        try:
            yield session
        except Exception as e:
            await session.rollback()
            raise
        finally:
            await session.close()

async def get_pg_connection():
    """Get raw PostgreSQL connection from pool"""
    if not pg_pool:
        raise RuntimeError("PostgreSQL pool not initialized")
    
    async with pg_pool.acquire() as connection:
        yield connection

async def test_connection() -> bool:
    """Test database connectivity"""
    try:
        if pg_pool:
            async with pg_pool.acquire() as conn:
                await conn.fetchval("SELECT 1")
            return True
        return False
    except Exception as e:
        logger.error(f"Database connection test failed: {e}")
        return False

async def create_tables():
    """Create database tables"""
    try:
        if engine:
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            logger.info("Database tables created successfully")
    except Exception as e:
        logger.error(f"Failed to create tables: {e}")
        raise

async def drop_tables():
    """Drop all database tables (development only)"""
    if settings.is_production():
        raise RuntimeError("Cannot drop tables in production")
    
    try:
        if engine:
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.drop_all)
            logger.info("Database tables dropped successfully")
    except Exception as e:
        logger.error(f"Failed to drop tables: {e}")
        raise

class DatabaseHealthCheck:
    """Database health check utility"""
    
    @staticmethod
    async def check_connectivity() -> dict:
        """Check database connectivity and performance"""
        try:
            start_time = asyncio.get_event_loop().time()
            is_connected = await test_connection()
            response_time = (asyncio.get_event_loop().time() - start_time) * 1000
            
            return {
                "status": "healthy" if is_connected else "unhealthy",
                "connected": is_connected,
                "response_time_ms": round(response_time, 2),
                "pool_size": pg_pool.get_size() if pg_pool else 0,
                "pool_free": pg_pool.get_idle_size() if pg_pool else 0
            }
        except Exception as e:
            return {
                "status": "error",
                "connected": False,
                "error": str(e),
                "response_time_ms": 0,
                "pool_size": 0,
                "pool_free": 0
            }