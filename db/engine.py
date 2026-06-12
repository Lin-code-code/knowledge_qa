from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from core.config import db_conf, env_conf

ASYNC_DB_URL = (
    f"postgresql+asyncpg://{env_conf.DB_USER}:{env_conf.DB_PASSWORD}"
    f"@{env_conf.DB_HOST}:{env_conf.DB_PORT}/{env_conf.DB_NAME}"
)

engine = create_async_engine(
    ASYNC_DB_URL,
    pool_size=db_conf.get("async_pool_size", 10),
    max_overflow=db_conf.get("async_max_overflow", 10),
    pool_recycle=db_conf.get("pool_recycle", 3600),
    pool_pre_ping=db_conf.get("pool_pre_ping", True),
    echo=False,
)

async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)
