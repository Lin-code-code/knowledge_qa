"""主题路由结构化输出和降级测试。"""
import json
from datetime import datetime, timezone
from uuid import uuid4

from models.conversation import ConversationTopic, Message
from services.topic_router import TopicRouter


def test_parse_plain_json():
    decision = TopicRouter._parse(
        json.dumps(
            {
                "action": "CONTINUE",
                "topic_label": "纯棉T恤洗护",
                "intent": "washing_care",
                "canonical_query": "纯棉T恤怎么洗",
                "scope": "IN",
                "confidence": 0.94,
                "segments": [],
            },
            ensure_ascii=False,
        )
    )
    assert decision.action == "CONTINUE"
    assert decision.topic_label == "纯棉T恤洗护"
    assert decision.confidence == 0.94


def test_parse_markdown_and_extra_explanation():
    decision = TopicRouter._parse(
        '结果如下：\n```json\n{"action":"NEW_TOPIC","scope":"IN",'
        '"topic_label":"羽绒服洗护","intent":"washing_care",'
        '"canonical_query":"羽绒服怎么洗"}\n```\n'
    )
    assert decision.action == "NEW_TOPIC"
    assert decision.topic_label == "羽绒服洗护"


def test_parse_out_scope_overrides_action():
    decision = TopicRouter._parse(
        '{"action":"CONTINUE","scope":"OUT","canonical_query":"今天股票涨了吗"}'
    )
    assert decision.action == "OUT_OF_SCOPE"
    assert decision.scope == "OUT"


def test_parse_invalid_output_raises():
    try:
        TopicRouter._parse("无法解析")
    except ValueError:
        pass
    else:
        raise AssertionError("非法路由输出应触发降级异常")


def test_route_failure_uses_limited_context():
    class FailingModel:
        def __init__(self):
            self.prompt = ""

        def invoke(self, messages):
            self.prompt = messages[0].content
            raise RuntimeError("模型不可用")

    model = FailingModel()
    router = TopicRouter(model=model)
    topic = ConversationTopic(topic_label="当前主题", summary="只保留当前主题摘要")
    old = Message(
        topic_id=topic.id,
        turn_id=uuid4(),
        role="human",
        content="很旧的问题",
        created_at=datetime.now(timezone.utc),
    )
    recent = [
        old,
        Message(
            topic_id=topic.id,
            turn_id=uuid4(),
            role="human",
            content="最近的问题",
            created_at=datetime.now(timezone.utc),
        ),
        Message(
            topic_id=topic.id,
            turn_id=uuid4(),
            role="ai",
            content="最近的回答",
            created_at=datetime.now(timezone.utc),
        ),
    ]
    decision = router.route("当前问题", topic=topic, recent_messages=recent)

    assert decision.action == "CONTINUE"
    assert "很旧的问题" not in model.prompt
    assert "最近的问题" in model.prompt
