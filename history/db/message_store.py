from sqlalchemy import select, update, func
from sqlalchemy.ext.asyncio import AsyncSession
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage
from typing import List
from history.models import Conversation, Message
import uuid
from utils.config_handler import db_conf


MAX_MESSAGES = db_conf.get("max_messages", 30)
MAX_TOKENS = db_conf.get("max_tokens", 2000)


class AsyncMessageStore:
    """异步消息存储层，负责会话和消息的 CRUD"""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_conversation(self, user_id: str = "anonymous", title: str = "新对话") -> uuid.UUID:
        """创建新会话，返回 conversation_id"""
        conv = Conversation(user_id=user_id, title=title)
        self.session.add(conv)
        await self.session.commit()
        await self.session.refresh(conv)
        return conv.id

    async def get_recent_messages(self, conversation_id: uuid.UUID) -> List[BaseMessage]:
        """
        加载最近的对话历史，并进行上下文窗口裁剪：
        1. 按 created_at DESC 取最新 MAX_MESSAGES 条
        2. 从最旧消息开始累加，按每 4 字符 ≈ 1 token 估算，超过 MAX_TOKENS 时截断
        3. 返回按 created_at ASC 排序的消息列表
        """
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

        total_chars = sum(len(m.content) for m in records)
        total_est_tokens = total_chars / 4

        if total_est_tokens <= MAX_TOKENS:
            return [self._to_langchain(m) for m in records]

        result = []
        token_count = 0
        for m in reversed(records):
            est_tokens = len(m.content) / 4
            if token_count + est_tokens > MAX_TOKENS:
                break
            result.append(m)
            token_count += est_tokens

        result.reverse()
        return [self._to_langchain(m) for m in result]

    async def add_messages(self, conversation_id: uuid.UUID, messages: List[BaseMessage]):
        """
        批量写入消息，同时更新 conversations.updated_at
        在同一事务中完成，保证原子性
        """
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
        """获取用户的会话列表，按 updated_at DESC 排序"""
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
        """获取指定会话的消息列表，按 created_at ASC 排序"""
        stmt = (
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(Message.created_at.asc())
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def delete_conversation(self, conversation_id: uuid.UUID) -> bool:
        """
        删除指定会话及其所有消息
        依赖数据库 ON DELETE CASCADE 级联删除
        """
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
        """将数据库记录转为 LangChain Message"""
        if record.role == "human":
            return HumanMessage(content=record.content)
        elif record.role == "ai":
            return AIMessage(content=record.content)
        elif record.role == "system":
            return SystemMessage(content=record.content)
        return HumanMessage(content=record.content)

    @staticmethod
    def _role_from_langchain(msg: BaseMessage) -> str:
        """从 LangChain Message 提取 role 字符串"""
        if isinstance(msg, HumanMessage):
            return "human"
        elif isinstance(msg, AIMessage):
            return "ai"
        elif isinstance(msg, SystemMessage):
            return "system"
        return "human"
