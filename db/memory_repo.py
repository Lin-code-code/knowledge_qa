from datetime import datetime, timezone
import uuid
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from models.memory_item import MemoryItem


class MemoryRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def list_active(self, user_id: str, limit: int = 12) -> list[MemoryItem]:
        now = datetime.now(timezone.utc)
        result = await self.session.execute(
            select(MemoryItem)
            .where(
                MemoryItem.user_id == user_id,
                MemoryItem.status == "active",
                (MemoryItem.expires_at.is_(None) | (MemoryItem.expires_at > now)),
            )
            .order_by(MemoryItem.updated_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def upsert(
        self,
        *,
        user_id: str,
        memory_type: str,
        memory_key: str,
        content: str,
        source_message_id: int | None,
        confidence: float,
        expires_at=None,
    ) -> MemoryItem:
        result = await self.session.execute(
            select(MemoryItem).where(
                MemoryItem.user_id == user_id,
                MemoryItem.memory_key == memory_key,
            )
        )
        item = result.scalar_one_or_none()
        if item is None:
            item = MemoryItem(
                user_id=user_id,
                memory_type=memory_type,
                memory_key=memory_key,
                content=content,
                source_message_id=source_message_id,
                confidence=confidence,
                expires_at=expires_at,
                status="active",
            )
            self.session.add(item)
            await self.session.flush()
            await self.session.refresh(item)
            return item

        item.memory_type = memory_type
        item.content = content
        item.source_message_id = source_message_id
        item.confidence = confidence
        item.expires_at = expires_at
        item.status = "active"
        item.updated_at = func.now()
        return item

    async def delete_one(self, user_id: str, memory_id: uuid.UUID) -> bool:
        result = await self.session.execute(
            delete(MemoryItem).where(
                MemoryItem.user_id == user_id,
                MemoryItem.id == memory_id,
            )
        )
        return result.rowcount > 0

    async def delete_all(self, user_id: str) -> int:
        result = await self.session.execute(delete(MemoryItem).where(MemoryItem.user_id == user_id))
        return result.rowcount
