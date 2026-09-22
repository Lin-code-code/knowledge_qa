"""主题 API 的响应和归档行为测试。"""
from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import uuid4

from fastapi.testclient import TestClient

import api.chat as chat_api
import core.security as security_module
from db.session import get_db
from main import app


class FakeTopicStore:
    shared_topic = SimpleNamespace(
        id=uuid4(),
        topic_label="纯棉T恤洗护",
        last_intent="washing_care",
        scope_label="IN",
        confidence=0.94,
        status="active",
        summary="不向列表接口暴露",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )

    def __init__(self):
        self.topic = self.shared_topic

    async def list(self, _conversation_id):
        return [self.topic]

    async def get(self, _conversation_id, topic_id):
        return self.topic if str(topic_id) == str(self.topic.id) else None

    async def archive(self, topic_id):
        self.topic.status = "archived"
        return True


class FakeConversationRepository:
    topics = None

    def __init__(self, _db):
        self.topics = FakeTopicStore()

    async def get_conversation(self, _conversation_id):
        return SimpleNamespace(id=_conversation_id)


async def fake_db():
    yield object()


def test_topics_list_and_detail_do_not_expose_summary(monkeypatch):
    monkeypatch.setattr(security_module.env_conf, "API_KEYS", "")
    monkeypatch.setattr(chat_api, "ConversationRepository", FakeConversationRepository)
    app.dependency_overrides[get_db] = fake_db
    try:
        client = TestClient(app)
        conversation_id = str(uuid4())
        response = client.get(f"/api/chat/{conversation_id}/topics")
        assert response.status_code == 200
        assert response.json()["topics"][0]["topic_label"] == "纯棉T恤洗护"
        assert "summary" not in response.json()["topics"][0]

        topic_id = response.json()["topics"][0]["topic_id"]
        detail = client.get(f"/api/chat/{conversation_id}/topics/{topic_id}")
        assert detail.status_code == 200
        assert detail.json()["summary"] == "不向列表接口暴露"
    finally:
        app.dependency_overrides.pop(get_db, None)
