from uuid import UUID

from domain.entities import Conversation, Message
from domain.ports import ConversationRepositoryPort, TopicRepositoryPort


class ConversationService:
    def __init__(self, conversations: ConversationRepositoryPort, topics: TopicRepositoryPort):
        self.conversations = conversations
        self.topics = topics

    async def create(self, user_id: str, title: str, *, create_topic: bool = True) -> Conversation:
        item = await self.conversations.create(user_id, title)
        if create_topic:
            await self.topics.create(item.id)
        return item

    async def get_messages(self, conversation_id: UUID) -> list[Message]:
        return await self.conversations.get_messages(conversation_id)

    async def delete(self, conversation_id: UUID) -> bool:
        return await self.conversations.delete(conversation_id)

    # 注意：方法名 list 会遮蔽内置 list，故放在使用 list[...] 注解的方法之后。
    async def list(self, user_id: str) -> list[Conversation]:
        return await self.conversations.list_by_user(user_id)
