from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.engine import URL
from core.config import db_conf, env_conf


def build_async_db_url() -> URL:
    """构造异步 ORM 连接 URL，密码特殊字符由 URL.create 自动编码。"""
    return URL.create(
        "postgresql+asyncpg",
        username=env_conf.DB_USER,
        password=env_conf.DB_PASSWORD,
        host=env_conf.DB_HOST,
        port=env_conf.DB_PORT,
        database=env_conf.DB_NAME,
    )


ASYNC_DB_URL = build_async_db_url()

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
