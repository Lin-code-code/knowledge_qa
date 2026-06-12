from sqlalchemy import select, update, func
from sqlalchemy.ext.asyncio import AsyncSession
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage
from typing import List
from models.conversation import Conversation, Message
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

    async def create_conversation(self, user_id: str = "anonymous", title: str = "新对话") -> uuid.UUID:
        conv = Conversation(user_id=user_id, title=title)
        self.session.add(conv)
        await self.session.commit()
        await self.session.refresh(conv)
        return conv.id

    async def get_recent_messages(self, conversation_id: uuid.UUID) -> List[BaseMessage]:
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

    async def add_messages(self, conversation_id: uuid.UUID, messages: List[BaseMessage]):
        for msg in messages:
            record = Message(
                conversation_id=conversation_id,
                role=self._role_from_langchain(msg),
                content=msg.content,
            )
            self.session.add(record)

        await self.session.execute(
            update(Conversation)
            .where(Conversation.id == conversation_id)
            .values(updated_at=func.now())
        )

        await self.session.commit()

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
        await self.session.commit()
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
