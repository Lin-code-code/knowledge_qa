"""企业级会话记忆主流程测试。"""
import asyncio
from datetime import datetime, timezone
from functools import wraps
from uuid import UUID, uuid4

from domain.decisions import ChatAnswer, TopicDecision, TopicSegment
from domain.entities import Conversation, ConversationTopic, MemoryItem, Message
from domain.enums import Role, ScopeLabel, TopicStatus
from services.chat_service import ChatService
from services.context_builder import ContextBuilder


def run_async(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        return asyncio.run(func(*args, **kwargs))

    return wrapper


def make_topic(
    label="服装咨询",
    *,
    conversation_id=None,
    summary="",
    last_intent="general",
    status=TopicStatus.ACTIVE,
):
    now = datetime.now(timezone.utc)
    return ConversationTopic(
        id=uuid4(),
        conversation_id=conversation_id or uuid4(),
        topic_label=label,
        last_intent=last_intent,
        scope_label=ScopeLabel.IN,
        confidence=0.0,
        status=status,
        summary=summary,
        summary_version=0,
        created_at=now,
        updated_at=now,
    )


def make_memory(memory_key, content):
    now = datetime.now(timezone.utc)
    return MemoryItem(
        id=uuid4(),
        user_id="user",
        memory_type="preference",
        memory_key=memory_key,
        content=content,
        source_message_id=None,
        confidence=1.0,
        expires_at=None,
        status="active",
        created_at=now,
        updated_at=now,
    )


class FakeTopics:
    def __init__(self, active=None):
        self.active = active
        self.created = []
        self.switched = []
        self.summary_updates = []
        self.summary_update_result = True

    async def get_active(self, _conversation_id):
        return self.active

    async def create(self, conversation_id, topic_label="服装咨询", **kwargs):
        # 端口契约要求 conversation_id 为 UUID；替身在此显式锁定类型，
        # 避免调用方误把整个 Conversation 领域对象传进来还能"通过"。
        assert isinstance(conversation_id, UUID), f"conversation_id 应为 UUID，实收 {type(conversation_id)}"
        topic = make_topic(
            topic_label,
            conversation_id=conversation_id,
            last_intent=kwargs.get("intent"),
        )
        self.created.append(topic)
        self.active = topic
        return topic

    async def switch(self, conversation_id, topic_label, **kwargs):
        topic = await self.create(conversation_id, topic_label, **kwargs)
        self.switched.append(topic)
        return topic

    async def update_metadata(self, *_args, **_kwargs):
        return None

    async def update_summary(self, topic_id, summary, expected_version):
        self.summary_updates.append((topic_id, summary, expected_version))
        return self.summary_update_result


class FakeStore:
    """假的会话仓储（ConversationRepositoryPort）。"""

    def __init__(self, active=None, conversation_exists=True):
        self.topics = FakeTopics(active)
        self.added_turns = []
        self.created_conversations = 0
        self.conversation_exists = conversation_exists
        self.last_created = None

    async def get(self, conversation_id):
        if not self.conversation_exists:
            return None
        now = datetime.now(timezone.utc)
        return Conversation(
            id=conversation_id,
            user_id="anonymous",
            title="新对话",
            created_at=now,
            updated_at=now,
        )

    async def get_recent_topic_messages(self, _topic_id):
        return []

    async def create(self, user_id="anonymous", title="新对话"):
        # 端口契约 `create(...) -> Conversation`：必须返回领域对象而不是裸 UUID。
        now = datetime.now(timezone.utc)
        self.created_conversations += 1
        self.last_created = Conversation(
            id=uuid4(),
            user_id=user_id,
            title=title,
            created_at=now,
            updated_at=now,
        )
        return self.last_created

    async def add_turn(self, conversation_id, topic_id, user_content, assistant_content, **kwargs):
        human = Message(
            conversation_id=conversation_id,
            role=Role.HUMAN,
            content=user_content,
            id=1,
            topic_id=topic_id,
        )
        self.added_turns.append(
            {
                "conversation_id": conversation_id,
                "topic_id": topic_id,
                "user_content": user_content,
                "assistant_content": assistant_content,
                **kwargs,
            }
        )
        return human, Message(
            conversation_id=conversation_id,
            role=Role.AI,
            content=assistant_content,
            id=2,
            topic_id=topic_id,
        )


class FakeMemoryService:
    def __init__(self, items):
        self.items = items
        self.requested_user_ids = []
        self.selected_queries = []
        self.extract_calls = 0

    async def list_for_prompt(self, user_id):
        self.requested_user_ids.append(user_id)
        return self.items

    def select_for_query(self, memories, query, intent=None):
        self.selected_queries.append((query, intent))
        return self.items

    async def extract_and_save(self, **_kwargs):
        self.extract_calls += 1
        return None


class FakeGuard:
    refusal_text = "统一拒答"

    def check_question_scope(self, _query):
        return True

    def check(self, _query, answer):
        return True, answer


class FakeAgent:
    def __init__(self):
        self.calls = []

    async def execute(self, query, context, topic_label):
        self.calls.append((query, context))
        return ChatAnswer(answer="服装回答")


def make_service(store):
    service = ChatService(
        conversations=store,
        topics=store.topics,
        memory_service=None,
        context_builder=ContextBuilder(),
        topic_router=object(),
        guard=FakeGuard(),
        chat_agent=FakeAgent(),
        summary_agent=None,
    )
    service.memory_enabled = True
    return service


@run_async
async def test_clarify_does_not_call_agent(monkeypatch):
    store = FakeStore()
    service = make_service(store)
    agent = FakeAgent()
    monkeypatch.setattr(service, "_route", lambda *args, **kwargs: _async_result(
        TopicDecision(
            action="CLARIFY",
            needs_clarification=True,
            clarification_question="请问您指的是哪件T恤？",
        )
    ))
    service.chat_agent = agent

    result = await service.process_message("它怎么洗？", None)

    assert result.topic_action == "CLARIFY"
    assert result.answer == "请问您指的是哪件T恤？"
    assert agent.calls == []
    assert store.created_conversations == 1
    assert store.added_turns[0]["memory_eligible"] is False
    assert isinstance(store.last_created, Conversation)
    assert result.chat_id == str(store.last_created.id)


@run_async
async def test_out_of_scope_does_not_create_new_conversation(monkeypatch):
    store = FakeStore(conversation_exists=False)
    service = make_service(store)
    monkeypatch.setattr(service, "_route", lambda *args, **kwargs: _async_result(
        TopicDecision(action="OUT_OF_SCOPE", scope="OUT", canonical_query="股票行情")
    ))

    result = await service.process_message("今天股票涨了吗", None)

    assert result.topic_action == "OUT_OF_SCOPE"
    assert result.chat_id == ""
    assert store.created_conversations == 0
    assert store.added_turns == []


@run_async
async def test_new_topic_does_not_send_old_topic_messages(monkeypatch):
    old_topic = make_topic(
        "旧主题",
        summary="旧主题摘要",
        last_intent="washing_care",
    )
    store = FakeStore(active=old_topic)
    service = make_service(store)
    agent = FakeAgent()
    monkeypatch.setattr(service, "_route", lambda *args, **kwargs: _async_result(
        TopicDecision(
            action="NEW_TOPIC",
            topic_label="羽绒服洗护",
            intent="washing_care",
            canonical_query="羽绒服怎么洗",
        )
    ))
    service.chat_agent = agent

    chat_id = uuid4()
    result = await service.process_message("羽绒服怎么洗", chat_id)

    assert result.topic_action == "NEW_TOPIC"
    assert result.topic_id == str(store.topics.switched[0].id)
    assert agent.calls[0][0] == "羽绒服怎么洗"
    assert "旧主题摘要" not in agent.calls[0][1]
    assert store.added_turns[0]["topic_id"] == store.topics.switched[0].id


@run_async
async def test_continue_reuses_active_topic(monkeypatch):
    active = make_topic(
        "纯棉T恤洗护",
        summary="纯棉T恤洗护摘要",
        last_intent="washing_care",
    )
    store = FakeStore(active=active)
    service = make_service(store)
    agent = FakeAgent()
    monkeypatch.setattr(service, "_route", lambda *args, **kwargs: _async_result(
        TopicDecision(
            action="CONTINUE",
            topic_label="纯棉T恤洗护",
            intent="washing_care",
            canonical_query="那它怎么洗",
        )
    ))
    service.chat_agent = agent

    chat_id = uuid4()
    result = await service.process_message("那它怎么洗", chat_id)

    assert result.topic_action == "CONTINUE"
    assert result.topic_id == str(active.id)
    assert store.topics.created == []
    assert store.topics.switched == []
    assert "纯棉T恤洗护摘要" in agent.calls[0][1]


@run_async
async def test_first_message_creates_conversation_and_topic(monkeypatch):
    store = FakeStore()
    service = make_service(store)
    agent = FakeAgent()
    monkeypatch.setattr(service, "_route", lambda *args, **kwargs: _async_result(
        TopicDecision(
            action="CONTINUE",
            topic_label="纯棉T恤洗护",
            intent="washing_care",
            canonical_query="纯棉T恤会缩水吗",
        )
    ))
    service.chat_agent = agent

    result = await service.process_message("纯棉T恤会缩水吗", None)

    assert store.created_conversations == 1
    assert len(store.topics.created) == 1
    assert isinstance(store.last_created, Conversation)
    assert result.chat_id == str(store.last_created.id)
    assert result.chat_id == str(store.topics.created[0].conversation_id)
    assert result.topic_id == str(store.topics.created[0].id)


@run_async
async def test_summary_failure_does_not_break_answer(monkeypatch):
    store = FakeStore()
    service = make_service(store)
    agent = FakeAgent()
    monkeypatch.setattr(service, "_route", lambda *args, **kwargs: _async_result(
        TopicDecision(
            action="CONTINUE",
            topic_label="T恤洗护",
            intent="washing_care",
            canonical_query="纯棉T恤怎么洗",
        )
    ))
    service.chat_agent = agent

    class BrokenSummary:
        def summarize(self, *_args, **_kwargs):
            raise RuntimeError("摘要模型不可用")

    service.summary_agent = BrokenSummary()

    result = await service.process_message("纯棉T恤怎么洗", None)

    assert result.answer == "服装回答"
    assert store.topics.summary_updates == []


@run_async
async def test_summary_version_conflict_does_not_override(monkeypatch):
    store = FakeStore()
    store.topics.summary_update_result = False
    service = make_service(store)
    agent = FakeAgent()
    monkeypatch.setattr(service, "_route", lambda *args, **kwargs: _async_result(
        TopicDecision(
            action="CONTINUE",
            topic_label="T恤洗护",
            intent="washing_care",
            canonical_query="纯棉T恤怎么洗",
        )
    ))
    service.chat_agent = agent

    class OkSummary:
        def summarize(self, *_args, **_kwargs):
            return "更新后的摘要"

    service.summary_agent = OkSummary()

    result = await service.process_message("纯棉T恤怎么洗", None)

    assert result.answer == "服装回答"
    assert len(store.topics.summary_updates) == 1
    assert store.topics.summary_updates[0][2] == 0


@run_async
async def test_out_of_scope_not_saved_to_summary_or_memory(monkeypatch):
    active = make_topic(
        "T恤洗护",
        summary="旧摘要",
        last_intent="washing_care",
    )
    store = FakeStore(active=active)
    service = make_service(store)
    service.memory_service = FakeMemoryService([])
    monkeypatch.setattr(service, "_route", lambda *args, **kwargs: _async_result(
        TopicDecision(action="OUT_OF_SCOPE", scope="OUT", canonical_query="今天股票涨了吗")
    ))

    result = await service.process_message("今天股票涨了吗", uuid4())

    assert result.topic_action == "OUT_OF_SCOPE"
    assert store.added_turns[0]["is_refusal"] is True
    assert store.added_turns[0]["memory_eligible"] is False
    assert store.added_turns[0]["scope_label"] == "OUT"
    assert store.topics.summary_updates == []
    assert service.memory_service.extract_calls == 0


@run_async
async def test_agent_context_uses_filtered_preferences(monkeypatch):
    store = FakeStore()
    service = make_service(store)

    class FilteringMemoryService:
        def __init__(self):
            self.calls = []

        async def list_for_prompt(self, user_id):
            return [
                make_memory("size", "常用尺码 L"),
                make_memory("color", "偏好黑色"),
            ]

        def select_for_query(self, memories, query, intent=None):
            self.calls.append((query, intent))
            return [memory for memory in memories if memory.memory_key == "size"]

        async def extract_and_save(self, **_kwargs):
            return None

    service.memory_service = FilteringMemoryService()
    agent = FakeAgent()
    monkeypatch.setattr(service, "_route", lambda *args, **kwargs: _async_result(
        TopicDecision(
            action="CONTINUE",
            topic_label="T恤推荐",
            intent="recommendation",
            canonical_query="推荐一件T恤",
        )
    ))
    service.chat_agent = agent

    result = await service.process_message("推荐一件T恤", None, user_id="user-1")

    assert result.answer == "服装回答"
    assert service.memory_service.calls[0][0] == "推荐一件T恤"
    assert "常用尺码 L" in agent.calls[0][1]
    assert "偏好黑色" not in agent.calls[0][1]


@run_async
async def test_mixed_question_only_answers_in_scope_segment(monkeypatch):
    store = FakeStore()
    service = make_service(store)
    agent = FakeAgent()
    monkeypatch.setattr(service, "_route", lambda *args, **kwargs: _async_result(
        TopicDecision(
            action="MIXED",
            canonical_query="",
            segments=[
                TopicSegment(query="推荐一件羽绒服", scope="IN"),
                TopicSegment(query="今天股票涨了吗", scope="OUT"),
            ],
        )
    ))
    service.chat_agent = agent

    result = await service.process_message("帮我查股票，再推荐一件羽绒服", None)

    assert agent.calls[0][0] == "推荐一件羽绒服"
    assert "股票" not in agent.calls[0][0]
    assert "统一拒答" in result.answer
    assert store.added_turns[0]["memory_eligible"] is False


@run_async
async def test_memory_disabled_keeps_messages_without_creating_topic(monkeypatch):
    store = FakeStore()
    service = make_service(store)
    service.memory_enabled = False
    agent = FakeAgent()
    monkeypatch.setattr(service, "_route", lambda *args, **kwargs: _async_result(
        TopicDecision(
            action="CONTINUE",
            topic_label="服装咨询",
            intent="general",
            canonical_query="推荐一件T恤",
        )
    ))
    service.chat_agent = agent

    result = await service.process_message("推荐一件T恤", None)

    assert result.topic_id is None
    assert store.created_conversations == 1
    assert store.topics.created == []
    assert store.added_turns[0]["topic_id"] is None
    assert service.memory_service is None


@run_async
async def test_new_conversation_loads_existing_user_preferences(monkeypatch):
    store = FakeStore()
    service = make_service(store)
    memory_service = FakeMemoryService([make_memory("size", "常用尺码 L")])
    service.memory_service = memory_service
    agent = FakeAgent()
    monkeypatch.setattr(service, "_route", lambda *args, **kwargs: _async_result(
        TopicDecision(
            action="CONTINUE",
            topic_label="T恤推荐",
            intent="recommendation",
            canonical_query="推荐一件黑色T恤",
        )
    ))
    service.chat_agent = agent

    result = await service.process_message(
        "推荐一件黑色T恤",
        None,
        user_id="user-123",
    )

    assert result.chat_id
    assert memory_service.requested_user_ids == ["user-123"]
    assert agent.calls
    assert "常用尺码 L" in agent.calls[0][1]


def _async_result(value):
    async def wrapped(*_args, **_kwargs):
        return value

    return wrapped()
