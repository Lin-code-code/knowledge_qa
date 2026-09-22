from domain.decisions import ChatAnswer, MemoryCandidate, TopicDecision
from domain.entities import ConversationTopic
from domain.enums import ScopeLabel, TopicAction, TopicStatus
from agent.summary_agent import SummaryAgent
from agent.topic_router import TopicRouter


class FakeModel:
    def __init__(self, raw):
        self.raw = raw

    def invoke(self, _messages):
        return type("Response", (), {"content": self.raw})()


def test_topic_router_returns_domain_decision():
    raw = '{"action":"OUT_OF_SCOPE","scope":"OUT","confidence":0.9}'
    decision = TopicRouter(model=FakeModel(raw)).route("股票")
    assert isinstance(decision, TopicDecision)
    assert decision.action == TopicAction.OUT_OF_SCOPE
    assert decision.scope == ScopeLabel.OUT


def test_summary_agent_returns_raw_non_json_text():
    topic = ConversationTopic(
        id=__import__("uuid").uuid4(),
        conversation_id=__import__("uuid").uuid4(),
        topic_label="T恤",
        summary="",
        last_intent=None,
        scope_label=ScopeLabel.IN,
        confidence=0.0,
        status="active",
        summary_version=0,
        created_at=__import__("datetime").datetime.now(__import__("datetime").timezone.utc),
        updated_at=__import__("datetime").datetime.now(__import__("datetime").timezone.utc),
    )
    assert SummaryAgent(model=FakeModel("not-json")).summarize(topic, "问", "答") == "not-json"


def test_chat_answer_type_has_sources():
    value = ChatAnswer(answer="ok", sources=["a.txt"])
    assert value.sources == ["a.txt"]


def test_memory_candidate_type_is_stable():
    value = MemoryCandidate(memory_key="size", content="L", confidence=0.9)
    assert value.memory_key == "size"
