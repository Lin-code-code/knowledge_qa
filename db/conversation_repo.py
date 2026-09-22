from sqlalchemy import select, update, func
from sqlalchemy.ext.asyncio import AsyncSession
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage
from typing import List
from models.conversation import Conversation, Message
from db.topic_repo import TopicRepository
from db.memory_repo import MemoryRepository
import uuid
from core.config import db_conf


MAX_MESSAGES = db_conf.get("max_messages", 30)
MAX_TOKENS = db_conf.get("max_tokens", 2000)


def _estimate_tokens(text: str) -> int:
    chinese_chars = sum(1 for c in text if '\u4e00' <= c <= '\u9fff')
    other_chars = len(text) - chinese_chars
    return int(chinese_chars / 1.5 + other_chars / 4)


class ConversationRepository:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.topics = TopicRepository(session)
        self.memories = MemoryRepository(session)

    async def create_conversation(
        self,
        user_id: str = "anonymous",
        title: str = "新对话",
        *,
        create_topic: bool = True,
    ) -> uuid.UUID:
        conv = Conversation(user_id=user_id, title=title)
        self.session.add(conv)
        await self.session.flush()
        await self.session.refresh(conv)
        if create_topic:
            await self.topics.create(conv.id)
        return conv.id

    async def get_conversation(self, conversation_id: uuid.UUID) -> Conversation | None:
        result = await self.session.execute(
            select(Conversation).where(Conversation.id == conversation_id)
        )
        return result.scalar_one_or_none()

    async def get_recent_messages(self, conversation_id: uuid.UUID) -> List[BaseMessage]:
        topic = await self.topics.get_active(conversation_id)
        if topic is not None:
            records = await self.get_recent_topic_records(topic.id)
            return [self._to_langchain(m) for m in records]

        stmt = (
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(Message.created_at.desc())
            .limit(MAX_MESSAGES)
        )
        result = await self.session.execute(stmt)
        records = result.scalars().all()

        if not records:
            return []

        records.reverse()

        total_est_tokens = sum(_estimate_tokens(m.content) for m in records)

        if total_est_tokens <= MAX_TOKENS:
            return [self._to_langchain(m) for m in records]

        result = []
        token_count = 0
        for m in reversed(records):
            est_tokens = _estimate_tokens(m.content)
            if token_count + est_tokens > MAX_TOKENS:
                break
            result.append(m)
            token_count += est_tokens

        result.reverse()
        return [self._to_langchain(m) for m in result]

    async def get_recent_topic_records(
        self,
        topic_id: uuid.UUID | None,
        *,
        max_turns: int | None = None,
        max_tokens: int | None = None,
    ) -> list[Message]:
        max_turns = max_turns or db_conf.get("topic_recent_turns", 2)
        max_tokens = max_tokens or db_conf.get("context_max_tokens", MAX_TOKENS)
        stmt = (
            select(Message)
            .where(
                Message.topic_id == topic_id,
                Message.memory_eligible.is_(True),
                Message.is_refusal.is_(False),
                Message.scope_label != "OUT",
                Message.turn_id.is_not(None),
            )
            .order_by(Message.created_at.desc(), Message.id.desc())
            .limit(max_turns * 4)
        )
        result = await self.session.execute(stmt)
        records = list(result.scalars().all())
        by_turn: dict[uuid.UUID, list[Message]] = {}
        for record in records:
            by_turn.setdefault(record.turn_id, []).append(record)

        turns: list[list[Message]] = []
        for turn_records in by_turn.values():
            turn_records.sort(key=lambda item: (item.created_at, item.id))
            roles = {item.role for item in turn_records}
            if {"human", "ai"} <= roles:
                turns.append([item for item in turn_records if item.role in {"human", "ai"}])
        turns.sort(key=lambda items: (items[0].created_at, items[0].id))
        selected: list[Message] = []
        token_count = 0
        for turn in reversed(turns):
            turn_tokens = sum(_estimate_tokens(item.content) for item in turn)
            if len(selected) >= max_turns * 2 or token_count + turn_tokens > max_tokens:
                break
            selected[0:0] = turn
            token_count += turn_tokens
        return selected

    async def add_messages(
        self,
        conversation_id: uuid.UUID,
        messages: List[BaseMessage],
        *,
        topic_id: uuid.UUID | None = None,
        intent: str | None = None,
        scope_label: str = "IN",
        is_refusal: bool = False,
        memory_eligible: bool = True,
        turn_id: uuid.UUID | None = None,
    ):
        if topic_id is None:
            topic = await self.topics.get_active(conversation_id)
            topic_id = topic.id if topic else None
        turn_id = turn_id or uuid.uuid4()
        for msg in messages:
            record = Message(
                conversation_id=conversation_id,
                topic_id=topic_id,
                turn_id=turn_id,
                role=self._role_from_langchain(msg),
                content=msg.content,
                intent=intent,
                scope_label=scope_label,
                is_refusal=is_refusal,
                memory_eligible=memory_eligible,
            )
            self.session.add(record)

        await self.session.execute(
            update(Conversation)
            .where(Conversation.id == conversation_id)
            .values(updated_at=func.now())
        )

    async def add_turn(
        self,
        conversation_id: uuid.UUID,
        topic_id: uuid.UUID,
        user_content: str,
        assistant_content: str,
        *,
        intent: str,
        scope_label: str = "IN",
        is_refusal: bool = False,
        memory_eligible: bool = True,
    ) -> tuple[Message, Message]:
        turn_id = uuid.uuid4()
        human = Message(
            conversation_id=conversation_id,
            topic_id=topic_id,
            turn_id=turn_id,
            role="human",
            content=user_content,
            intent=intent,
            scope_label=scope_label,
            is_refusal=is_refusal,
            memory_eligible=memory_eligible,
        )
        assistant = Message(
            conversation_id=conversation_id,
            topic_id=topic_id,
            turn_id=turn_id,
            role="ai",
            content=assistant_content,
            intent=intent,
            scope_label=scope_label,
            is_refusal=is_refusal,
            memory_eligible=memory_eligible,
        )
        self.session.add_all([human, assistant])
        await self.session.execute(
            update(Conversation)
            .where(Conversation.id == conversation_id)
            .values(updated_at=func.now())
        )
        await self.session.flush()
        return human, assistant

    async def list_conversations(self, user_id: str = "anonymous", limit: int = 50, offset: int = 0) -> list:
        stmt = (
            select(Conversation)
            .where(Conversation.user_id == user_id)
            .order_by(Conversation.updated_at.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_messages(self, conversation_id: uuid.UUID, limit: int = 100) -> list:
        stmt = (
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(Message.created_at.asc())
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def delete_conversation(self, conversation_id: uuid.UUID) -> bool:
        result = await self.session.execute(
            select(Conversation).where(Conversation.id == conversation_id)
        )
        conv = result.scalar_one_or_none()
        if conv is None:
            return False

        await self.session.delete(conv)
        return True

    @staticmethod
    def _to_langchain(record: Message) -> BaseMessage:
        if record.role == "human":
            return HumanMessage(content=record.content)
        elif record.role == "ai":
            return AIMessage(content=record.content)
        elif record.role == "system":
            return SystemMessage(content=record.content)
        return HumanMessage(content=record.content)

    @staticmethod
    def _role_from_langchain(msg: BaseMessage) -> str:
        if isinstance(msg, HumanMessage):
            return "human"
        elif isinstance(msg, AIMessage):
            return "ai"
        elif isinstance(msg, SystemMessage):
            return "system"
        return "human"
