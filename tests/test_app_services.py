"""应用服务（会话、主题、记忆）契约测试。"""
import asyncio
from datetime import datetime, timezone
from uuid import uuid4

from domain.entities import Conversation, MemoryItem
from domain.errors import TopicNotFoundError
from services.conversation_service import ConversationService
from services.memory_service import MemoryService
from services.topic_service import TopicService


class FakeConversationRepo:
    def __init__(self):
        self.items = {}

    async def create(self, user_id, title):
        now = datetime.now(timezone.utc)
        item = Conversation(uuid4(), user_id, title, now, now)
        self.items[item.id] = item
        return item

    async def get(self, conversation_id):
        return self.items.get(conversation_id)

    async def list_by_user(self, user_id, limit=50, offset=0):
        return [item for item in self.items.values() if item.user_id == user_id]

    async def delete(self, conversation_id):
        return self.items.pop(conversation_id, None) is not None

    async def get_messages(self, conversation_id, limit=100):
        return []


class FakeTopicRepo:
    def __init__(self):
        self.archived = []

    async def create(self, conversation_id, topic_label="服装咨询", **kwargs):
        from domain.entities import ConversationTopic
        from domain.enums import ScopeLabel, TopicStatus

        now = datetime.now(timezone.utc)
        return ConversationTopic(
            uuid4(), conversation_id, topic_label, "", kwargs.get("intent"),
            ScopeLabel.IN, 0.0, TopicStatus.ACTIVE, 0, now, now,
        )

    async def archive(self, topic_id):
        self.archived.append(topic_id)
        return True

    async def get(self, conversation_id, topic_id):
        return None


class FakeMemoryRepo:
    async def list_active(self, user_id, limit=12):
        now = datetime.now(timezone.utc)
        return [
            MemoryItem(
                uuid4(), user_id, "preference", "size", "常用尺码 L", None,
                0.95, None, "active", now, now,
            )
        ]

    async def delete_one(self, user_id, memory_id):
        return True

    async def delete_all(self, user_id):
        return 2


def test_conversation_service_creates_default_topic():
    async def scenario():
        conversations = FakeConversationRepo()
        topics = FakeTopicRepo()
        service = ConversationService(conversations, topics)
        item = await service.create("u1", "新对话")
        assert (await service.list("u1"))[0].id == item.id
    asyncio.run(scenario())


def test_topic_service_maps_missing_topic_to_domain_error():
    async def scenario():
        service = TopicService(FakeConversationRepo(), FakeTopicRepo())
        try:
            await service.get(uuid4(), uuid4())
        except TopicNotFoundError:
            return
        raise AssertionError("应抛出 TopicNotFoundError")
    asyncio.run(scenario())


def test_memory_service_lists_and_deletes():
    async def scenario():
        service = MemoryService(FakeMemoryRepo())
        memories = await service.list_active("u1")
        assert memories[0].memory_key == "size"
        assert await service.delete_all("u1") == 2
    asyncio.run(scenario())
