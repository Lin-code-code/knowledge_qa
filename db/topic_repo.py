from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from models.conversation import ConversationTopic
import uuid


class TopicRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_active(self, conversation_id: uuid.UUID) -> ConversationTopic | None:
        result = await self.session.execute(
            select(ConversationTopic)
            .where(
                ConversationTopic.conversation_id == conversation_id,
                ConversationTopic.status == "active",
            )
            .order_by(ConversationTopic.updated_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def create(
        self,
        conversation_id: uuid.UUID,
        topic_label: str = "服装咨询",
        *,
        intent: str | None = None,
        scope_label: str = "IN",
        confidence: float = 0.0,
    ) -> ConversationTopic:
        topic = ConversationTopic(
            conversation_id=conversation_id,
            topic_label=topic_label[:256] or "服装咨询",
            last_intent=intent,
            scope_label=scope_label,
            confidence=confidence,
            status="active",
        )
        self.session.add(topic)
        await self.session.flush()
        await self.session.refresh(topic)
        return topic

    async def archive(self, topic_id: uuid.UUID) -> bool:
        result = await self.session.execute(
            update(ConversationTopic)
            .where(ConversationTopic.id == topic_id, ConversationTopic.status == "active")
            .values(status="archived", updated_at=func.now())
        )
        return result.rowcount > 0

    async def switch_topic(
        self,
        conversation_id: uuid.UUID,
        topic_label: str,
        *,
        intent: str | None = None,
        scope_label: str = "IN",
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

    async def get(self, conversation_id: uuid.UUID, topic_id: uuid.UUID) -> ConversationTopic | None:
        result = await self.session.execute(
            select(ConversationTopic).where(
                ConversationTopic.conversation_id == conversation_id,
                ConversationTopic.id == topic_id,
            )
        )
        return result.scalar_one_or_none()

    async def list(self, conversation_id: uuid.UUID) -> list[ConversationTopic]:
        result = await self.session.execute(
            select(ConversationTopic)
            .where(ConversationTopic.conversation_id == conversation_id)
            .order_by(ConversationTopic.updated_at.desc())
        )
        return list(result.scalars().all())

    async def update_metadata(
        self,
        topic_id: uuid.UUID,
        *,
        topic_label: str | None = None,
        intent: str | None = None,
        scope_label: str | None = None,
        confidence: float | None = None,
    ) -> None:
        values = {"updated_at": func.now()}
        if topic_label:
            values["topic_label"] = topic_label[:256]
        if intent is not None:
            values["last_intent"] = intent[:64]
        if scope_label is not None:
            values["scope_label"] = scope_label[:16]
        if confidence is not None:
            values["confidence"] = confidence
        await self.session.execute(
            update(ConversationTopic).where(ConversationTopic.id == topic_id).values(**values)
        )

    async def update_summary(self, topic_id: uuid.UUID, summary: str, expected_version: int) -> bool:
        result = await self.session.execute(
            update(ConversationTopic)
            .where(
                ConversationTopic.id == topic_id,
                ConversationTopic.summary_version == expected_version,
            )
            .values(
                summary=summary,
                summary_version=ConversationTopic.summary_version + 1,
                updated_at=func.now(),
            )
        )
        return result.rowcount > 0
