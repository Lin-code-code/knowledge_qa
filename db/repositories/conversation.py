"""会话与消息的 SQLAlchemy 仓储实现。

事务边界由 ``db/session.py:get_db`` 统一管理，仓储只做 ``flush()``/``refresh()``，
不调用 ``commit()``。所有公开返回值均为 ``domain.entities`` 领域对象。
"""

from uuid import UUID, uuid4

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import db_conf
from core.tokens import estimate_tokens
from db.mappers import to_conversation, to_message
from db.models.conversation import Conversation as ConversationModel
from db.models.conversation import Message as MessageModel
from domain.entities import Conversation, Message
from domain.enums import ScopeLabel


class SqlAlchemyConversationRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, user_id: str, title: str) -> Conversation:
        row = ConversationModel(user_id=user_id, title=title)
        self.session.add(row)
        await self.session.flush()
        await self.session.refresh(row)
        return to_conversation(row)

    async def get(self, conversation_id: UUID) -> Conversation | None:
        row = await self.session.get(ConversationModel, conversation_id)
        return to_conversation(row) if row else None

    async def list_by_user(self, user_id: str, limit: int = 50, offset: int = 0) -> list[Conversation]:
        result = await self.session.execute(
            select(ConversationModel)
            .where(ConversationModel.user_id == user_id)
            .order_by(ConversationModel.updated_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return [to_conversation(row) for row in result.scalars().all()]

    async def delete(self, conversation_id: UUID) -> bool:
        row = await self.session.get(ConversationModel, conversation_id)
        if row is None:
            return False
        await self.session.delete(row)
        return True

    async def get_messages(self, conversation_id: UUID, limit: int = 100) -> list[Message]:
        result = await self.session.execute(
            select(MessageModel)
            .where(MessageModel.conversation_id == conversation_id)
            .order_by(MessageModel.created_at.asc())
            .limit(limit)
        )
        return [to_message(row) for row in result.scalars().all()]

    async def get_recent_topic_messages(
        self,
        topic_id: UUID | None,
        *,
        max_turns: int | None = None,
        max_tokens: int | None = None,
    ) -> list[Message]:
        max_turns = max_turns or db_conf.get("topic_recent_turns", 2)
        max_tokens = max_tokens or db_conf.get("context_max_tokens", 2000)
        stmt = (
            select(MessageModel)
            .where(
                MessageModel.topic_id == topic_id,
                MessageModel.memory_eligible.is_(True),
                MessageModel.is_refusal.is_(False),
                MessageModel.scope_label != "OUT",
                MessageModel.turn_id.is_not(None),
            )
            .order_by(MessageModel.created_at.desc(), MessageModel.id.desc())
            .limit(max_turns * 4)
        )
        result = await self.session.execute(stmt)
        records = list(result.scalars().all())
        by_turn: dict[UUID, list[MessageModel]] = {}
        for record in records:
            by_turn.setdefault(record.turn_id, []).append(record)

        turns: list[list[MessageModel]] = []
        for turn_records in by_turn.values():
            turn_records.sort(key=lambda item: (item.created_at, item.id))
            roles = {item.role for item in turn_records}
            if {"human", "ai"} <= roles:
                turns.append([item for item in turn_records if item.role in {"human", "ai"}])
        turns.sort(key=lambda items: (items[0].created_at, items[0].id))

        selected: list[MessageModel] = []
        token_count = 0
        for turn in reversed(turns):
            turn_tokens = sum(estimate_tokens(item.content) for item in turn)
            if len(selected) >= max_turns * 2 or token_count + turn_tokens > max_tokens:
                break
            selected[0:0] = turn
            token_count += turn_tokens
        return [to_message(item) for item in selected]

    async def add_turn(
        self,
        conversation_id: UUID,
        topic_id: UUID | None,
        user_content: str,
        assistant_content: str,
        *,
        intent: str,
        scope_label: ScopeLabel = ScopeLabel.IN,
        is_refusal: bool = False,
        memory_eligible: bool = True,
    ) -> tuple[Message, Message]:
        turn_id = uuid4()
        human = MessageModel(
            conversation_id=conversation_id,
            topic_id=topic_id,
            turn_id=turn_id,
            role="human",
            content=user_content,
            intent=intent,
            scope_label=scope_label.value,
            is_refusal=is_refusal,
            memory_eligible=memory_eligible,
        )
        assistant = MessageModel(
            conversation_id=conversation_id,
            topic_id=topic_id,
            turn_id=turn_id,
            role="ai",
            content=assistant_content,
            intent=intent,
            scope_label=scope_label.value,
            is_refusal=is_refusal,
            memory_eligible=memory_eligible,
        )
        self.session.add_all([human, assistant])
        await self.session.execute(
            update(ConversationModel)
            .where(ConversationModel.id == conversation_id)
            .values(updated_at=func.now())
        )
        await self.session.flush()
        return to_message(human), to_message(assistant)
