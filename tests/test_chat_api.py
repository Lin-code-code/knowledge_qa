"""聊天接口错误语义测试（不依赖数据库与模型服务）。"""
from datetime import datetime, timezone
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

import core.security as security_module
from api.dependencies import get_chat_service, get_conversation_service
from domain.entities import Message
from domain.enums import Role
from main import app
from services.chat_service import ChatResult

client = TestClient(app)


@pytest.fixture(autouse=True)
def no_api_key(monkeypatch):
    monkeypatch.setattr(security_module.env_conf, "API_KEYS", "")


@pytest.fixture(autouse=True)
def clean_dependency_overrides():
    yield
    app.dependency_overrides.pop(get_chat_service, None)
    app.dependency_overrides.pop(get_conversation_service, None)


class FakeChatService:
    def __init__(self, result=None):
        self.process_message = AsyncMock(return_value=result)


def use_chat_service(result=None):
    """用 fake ChatService 覆盖依赖，避免构造真实 Agent。"""
    fake = FakeChatService(result)
    app.dependency_overrides[get_chat_service] = lambda: fake
    return fake


def test_empty_message_returns_400():
    use_chat_service(ChatResult(answer="", sources=[], chat_id="", topic_id=None, topic_action="CONTINUE"))
    resp = client.post("/api/chat/", json={"message": "   "})
    assert resp.status_code == 400


def test_invalid_chat_id_returns_400():
    use_chat_service(ChatResult(answer="", sources=[], chat_id="", topic_id=None, topic_action="CONTINUE"))
    resp = client.post("/api/chat/", json={"message": "你好", "chatId": "not-a-uuid"})
    assert resp.status_code == 400
    assert resp.json()["detail"] == "chatId 格式无效"


def test_valid_chat_id_enters_service():
    """合法 chatId 通过 API 校验并正常进入业务流程。"""
    chat_id = str(UUID("12345678-1234-5678-1234-567812345678"))
    fake = use_chat_service(
        ChatResult(answer="ok", sources=[], chat_id=chat_id, topic_id=None, topic_action="CONTINUE")
    )

    resp = client.post("/api/chat/", json={"message": "纯棉T恤怎么洗", "chatId": chat_id})

    assert resp.status_code == 200
    assert resp.json()["chatId"] == chat_id
    fake.process_message.assert_awaited_once()


def test_chat_response_includes_topic_fields():
    """首轮问题和同 chatId 追问都返回 topicId/topicAction，兼容前端旧字段。"""
    chat_id = str(UUID("12345678-1234-5678-1234-567812345678"))
    topic_id = str(uuid4())
    use_chat_service(
        ChatResult(
            answer="服装回答",
            sources=[],
            chat_id=chat_id,
            topic_id=topic_id,
            topic_action="CONTINUE",
        )
    )

    resp = client.post("/api/chat/", json={"message": "那它怎么洗", "chatId": chat_id})

    body = resp.json()
    assert resp.status_code == 200
    assert body["chatId"] == chat_id
    assert body["topicId"] == topic_id
    assert body["topicAction"] == "CONTINUE"


def test_out_of_scope_response_is_compatible():
    use_chat_service(
        ChatResult(
            answer="统一拒答",
            sources=[],
            chat_id="",
            topic_id=None,
            topic_action="OUT_OF_SCOPE",
        )
    )
    resp = client.post("/api/chat/", json={"message": "今天股票涨了吗"})

    assert resp.status_code == 200
    assert resp.json()["topicAction"] == "OUT_OF_SCOPE"
    assert resp.json()["answer"] == "统一拒答"


def test_messages_endpoint_keeps_legacy_format():
    """迁移后消息带 topic 字段，但列表接口仍只暴露旧字段。"""
    chat_id = str(UUID("12345678-1234-5678-1234-567812345678"))

    class FakeConversationService:
        async def get_messages(self, conversation_id):
            return [
                Message(
                    conversation_id=conversation_id,
                    role=Role.HUMAN,
                    content="纯棉T恤会缩水吗",
                    created_at=datetime.now(timezone.utc),
                    topic_id=uuid4(),
                    turn_id=uuid4(),
                )
            ]

    app.dependency_overrides[get_conversation_service] = lambda: FakeConversationService()
    resp = client.get(f"/api/chat/{chat_id}/messages")

    assert resp.status_code == 200
    item = resp.json()["messages"][0]
    assert set(item.keys()) == {"role", "content", "created_at"}
