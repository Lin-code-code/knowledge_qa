"""长期记忆的 SQLAlchemy 仓储实现。

事务边界由 ``db/session.py:get_db`` 统一管理，仓储只做 ``flush()``/``refresh()``，
不调用 ``commit()``。所有公开返回值均为 ``domain.entities`` 领域对象。
"""

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from db.mappers import to_memory_item
from db.models.memory_item import MemoryItem as MemoryModel
from domain.entities import MemoryItem


class SqlAlchemyMemoryRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def list_active(self, user_id: str, limit: int = 12) -> list[MemoryItem]:
        now = datetime.now(timezone.utc)
        result = await self.session.execute(
            select(MemoryModel)
            .where(
                MemoryModel.user_id == user_id,
                MemoryModel.status == "active",
                (MemoryModel.expires_at.is_(None) | (MemoryModel.expires_at > now)),
            )
            .order_by(MemoryModel.updated_at.desc())
            .limit(limit)
        )
        return [to_memory_item(row) for row in result.scalars().all()]

    async def upsert(
        self,
        *,
        user_id: str,
        memory_type: str,
        memory_key: str,
        content: str,
        source_message_id: int | None,
        confidence: float,
        expires_at: datetime | None = None,
    ) -> MemoryItem:
        result = await self.session.execute(
            select(MemoryModel).where(
                MemoryModel.user_id == user_id,
                MemoryModel.memory_key == memory_key,
            )
        )
        row = result.scalar_one_or_none()
        if row is None:
            row = MemoryModel(
                user_id=user_id,
                memory_type=memory_type,
                memory_key=memory_key,
                content=content,
                source_message_id=source_message_id,
                confidence=confidence,
                expires_at=expires_at,
                status="active",
            )
            self.session.add(row)
            await self.session.flush()
            await self.session.refresh(row)
            return to_memory_item(row)

        row.memory_type = memory_type
        row.content = content
        row.source_message_id = source_message_id
        row.confidence = confidence
        row.expires_at = expires_at
        row.status = "active"
        row.updated_at = func.now()
        # 与插入分支同理：func.now() 是 SQL 表达式而非 datetime，必须 flush 后 refresh 才能取回真实值，
        # 否则端口声明的 MemoryItem.updated_at 会变成表达式对象（调用方 .isoformat() 会报 AttributeError）。
        await self.session.flush()
        await self.session.refresh(row)
        return to_memory_item(row)

    async def delete_one(self, user_id: str, memory_id: UUID) -> bool:
        result = await self.session.execute(
            delete(MemoryModel).where(
                MemoryModel.user_id == user_id,
                MemoryModel.id == memory_id,
            )
        )
        return result.rowcount > 0

    async def delete_all(self, user_id: str) -> int:
        result = await self.session.execute(delete(MemoryModel).where(MemoryModel.user_id == user_id))
        return result.rowcount
