"""会话主题的 SQLAlchemy 仓储实现。

事务边界由 ``db/session.py:get_db`` 统一管理，仓储只做 ``flush()``/``refresh()``，
不调用 ``commit()``。所有公开返回值均为 ``domain.entities`` 领域对象。
"""

from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from db.mappers import to_topic
from db.models.conversation import ConversationTopic as TopicModel
from domain.entities import ConversationTopic
from domain.enums import ScopeLabel


class SqlAlchemyTopicRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_active(self, conversation_id: UUID) -> ConversationTopic | None:
        result = await self.session.execute(
            select(TopicModel)
            .where(TopicModel.conversation_id == conversation_id, TopicModel.status == "active")
            .order_by(TopicModel.updated_at.desc())
            .limit(1)
        )
        row = result.scalar_one_or_none()
        return to_topic(row) if row else None

    async def create(
        self,
        conversation_id: UUID,
        topic_label: str = "服装咨询",
        *,
        intent: str | None = None,
        scope_label: ScopeLabel = ScopeLabel.IN,
        confidence: float = 0.0,
    ) -> ConversationTopic:
        row = TopicModel(
            conversation_id=conversation_id,
            topic_label=topic_label[:256] or "服装咨询",
            last_intent=intent,
            scope_label=scope_label.value,
            confidence=confidence,
            status="active",
        )
        self.session.add(row)
        await self.session.flush()
        await self.session.refresh(row)
        return to_topic(row)

    async def switch(
        self,
        conversation_id: UUID,
        topic_label: str,
        *,
        intent: str | None = None,
        scope_label: ScopeLabel = ScopeLabel.IN,
        confidence: float = 0.0,
    ) -> ConversationTopic:
        active = await self.get_active(conversation_id)
        if active is not None:
            await self.archive(active.id)
        return await self.create(
            conversation_id,
            topic_label,
            intent=intent,
            scope_label=scope_label,
            confidence=confidence,
        )

    async def get(self, conversation_id: UUID, topic_id: UUID) -> ConversationTopic | None:
        result = await self.session.execute(
            select(TopicModel).where(
                TopicModel.conversation_id == conversation_id,
                TopicModel.id == topic_id,
            )
        )
        row = result.scalar_one_or_none()
        return to_topic(row) if row else None

    async def list(self, conversation_id: UUID) -> list[ConversationTopic]:
        result = await self.session.execute(
            select(TopicModel)
            .where(TopicModel.conversation_id == conversation_id)
            .order_by(TopicModel.updated_at.desc())
        )
        return [to_topic(row) for row in result.scalars().all()]

    async def archive(self, topic_id: UUID) -> bool:
        result = await self.session.execute(
            update(TopicModel)
            .where(TopicModel.id == topic_id, TopicModel.status == "active")
            .values(status="archived", updated_at=func.now())
        )
        return result.rowcount > 0

    async def update_metadata(
        self,
        topic_id: UUID,
        *,
        topic_label: str | None = None,
        intent: str | None = None,
        scope_label: ScopeLabel | None = None,
        confidence: float | None = None,
    ) -> None:
        values = {"updated_at": func.now()}
        if topic_label:
            values["topic_label"] = topic_label[:256]
        if intent is not None:
            values["last_intent"] = intent[:64]
        if scope_label is not None:
            values["scope_label"] = scope_label.value[:16]
        if confidence is not None:
            values["confidence"] = confidence
        await self.session.execute(
            update(TopicModel).where(TopicModel.id == topic_id).values(**values)
        )

    async def update_summary(self, topic_id: UUID, summary: str, expected_version: int) -> bool:
        result = await self.session.execute(
            update(TopicModel)
            .where(
                TopicModel.id == topic_id,
                TopicModel.summary_version == expected_version,
            )
            .values(
                summary=summary,
                summary_version=TopicModel.summary_version + 1,
                updated_at=func.now(),
            )
        )
        return result.rowcount > 0
