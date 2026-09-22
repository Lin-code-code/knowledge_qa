from uuid import UUID

from domain.entities import ConversationTopic
from domain.errors import ConversationNotFoundError, TopicNotFoundError
from domain.ports import ConversationRepositoryPort, TopicRepositoryPort


class TopicService:
    def __init__(self, conversations: ConversationRepositoryPort, topics: TopicRepositoryPort):
        self.conversations = conversations
        self.topics = topics

    async def list(self, conversation_id: UUID) -> list[ConversationTopic]:
        if await self.conversations.get(conversation_id) is None:
            raise ConversationNotFoundError(str(conversation_id))
        return await self.topics.list(conversation_id)

    async def get(self, conversation_id: UUID, topic_id: UUID) -> ConversationTopic:
        item = await self.topics.get(conversation_id, topic_id)
        if item is None:
            raise TopicNotFoundError(str(topic_id))
        return item

    async def archive(self, conversation_id: UUID, topic_id: UUID) -> None:
        await self.get(conversation_id, topic_id)
        await self.topics.archive(topic_id)
