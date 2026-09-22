"""主题 API 的响应和归档行为测试。"""
from datetime import datetime, timezone
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

import core.security as security_module
from api.dependencies import get_topic_service
from domain.entities import ConversationTopic
from domain.enums import ScopeLabel, TopicStatus
from domain.errors import TopicNotFoundError
from main import app


def make_topic(summary="不向列表接口暴露"):
    now = datetime.now(timezone.utc)
    return ConversationTopic(
        id=uuid4(),
        conversation_id=uuid4(),
        topic_label="纯棉T恤洗护",
        last_intent="washing_care",
        scope_label=ScopeLabel.IN,
        confidence=0.94,
        status=TopicStatus.ACTIVE,
        summary=summary,
        summary_version=0,
        created_at=now,
        updated_at=now,
    )


class FakeTopicService:
    def __init__(self, topic):
        self.topic = topic

    async def list(self, _conversation_id):
        return [self.topic]

    async def get(self, _conversation_id, topic_id):
        if str(topic_id) != str(self.topic.id):
            raise TopicNotFoundError(str(topic_id))
        return self.topic

    async def archive(self, _conversation_id, topic_id):
        await self.get(_conversation_id, topic_id)
        self.topic.status = TopicStatus.ARCHIVED


@pytest.fixture(autouse=True)
def no_api_key(monkeypatch):
    monkeypatch.setattr(security_module.env_conf, "API_KEYS", "")


def test_topics_list_and_detail_do_not_expose_summary():
    service = FakeTopicService(make_topic())
    app.dependency_overrides[get_topic_service] = lambda: service
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
        app.dependency_overrides.pop(get_topic_service, None)
