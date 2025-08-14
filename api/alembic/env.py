from logging.config import fileConfig
import sys
from pathlib import Path
import importlib
import pkgutil

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import create_async_engine, AsyncEngine

# Alembic Config
config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Ensure project root (api/) is on sys.path
CURRENT_FILE = Path(__file__).resolve()
API_DIR = CURRENT_FILE.parents[1]
if str(API_DIR) not in sys.path:
    sys.path.insert(0, str(API_DIR))

# Import app settings and Base
from config.settings import get_settings  # noqa: E402
from models.database.base import Base  # noqa: E402

settings = get_settings()
DATABASE_URL = settings.DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://")

# Autoload all model modules so Base.metadata is populated
MODELS_PACKAGE_PATH = API_DIR / "models"

def _import_all_models(package_path: Path, package_name: str = "models") -> None:
    if not package_path.exists():
        return
    for module_info in pkgutil.walk_packages([str(package_path)], prefix=f"{package_name}."):
        try:
            importlib.import_module(module_info.name)
        except Exception:
            # Ignore import errors in migration context
            pass

_import_all_models(MODELS_PACKAGE_PATH)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(
        url=DATABASE_URL,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        compare_server_default=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def _run_sync_migrations(connection: Connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
        compare_server_default=True,
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    engine: AsyncEngine = create_async_engine(DATABASE_URL, poolclass=pool.NullPool)
    async with engine.connect() as connection:
        await connection.run_sync(_run_sync_migrations)
    await engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    import asyncio
    asyncio.run(run_migrations_online())
