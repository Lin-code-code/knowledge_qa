from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from typing import AsyncGenerator
from utils.config_handler import db_conf

ASYNC_DB_URL = (
    f"postgresql+asyncpg://{db_conf['user']}:{db_conf['password']}"
    f"@{db_conf['host']}:{db_conf['port']}/{db_conf['dbname']}"
)

engine = create_async_engine(
    ASYNC_DB_URL,
    pool_size=db_conf.get("async_pool_size", 10),
    max_overflow=db_conf.get("async_max_overflow", 10),
    pool_recycle=db_conf.get("pool_recycle", 3600),
    pool_pre_ping=db_conf.get("pool_pre_ping", True),
    echo=True,
)

# 创建异步会话工厂
async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


# 获取异步数据库 session
async def get_db():
    """FastAPI 依赖注入：获取异步数据库 session"""
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception as e:
            await session.rollback()
            raise e
        finally:
            await session.close()


async def close_db():
    """应用关闭时清理连接池"""
    await engine.dispose()
