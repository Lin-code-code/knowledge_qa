from sqlalchemy.ext.asyncio import AsyncSession
from db.engine import engine, async_session_factory


async def get_db():
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
    await engine.dispose()
