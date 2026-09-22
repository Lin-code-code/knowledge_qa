"""长期偏好按意图筛选与匿名保护测试。"""
import asyncio
from types import SimpleNamespace

from services.memory_service import MemoryService


def _memory(key, content):
    return SimpleNamespace(memory_key=key, content=content)


def _service():
    service = MemoryService.__new__(MemoryService)
    service.prompt = ""
    service.threshold = 0.8
    service.model = None
    return service


def test_select_for_query_filters_by_query_keywords():
    service = _service()
    memories = [
        _memory("size", "常用尺码 L"),
        _memory("color", "偏好黑色"),
        _memory("material", "偏好纯棉"),
    ]

    selected = service.select_for_query(memories, "纯棉T恤怎么洗")

    assert [item.memory_key for item in selected] == ["material"]


def test_select_for_query_returns_all_for_shopping_intent():
    service = _service()
    memories = [
        _memory("size", "常用尺码 L"),
        _memory("color", "偏好黑色"),
        _memory("material", "偏好纯棉"),
        _memory("wearing_restriction", "不穿羊毛"),
    ]

    selected = service.select_for_query(memories, "帮我推荐一件T恤")

    assert {item.memory_key for item in selected} == {
        "size",
        "color",
        "material",
        "wearing_restriction",
    }


def test_select_for_query_honors_explicit_intent():
    service = _service()
    memories = [_memory("size", "常用尺码 L"), _memory("color", "偏好黑色")]

    selected = service.select_for_query(memories, "随便聊聊", intent="size")

    assert [item.memory_key for item in selected] == ["size"]


def test_select_for_query_returns_empty_for_unrelated_question():
    service = _service()
    memories = [_memory("size", "常用尺码 L"), _memory("color", "偏好黑色")]

    assert service.select_for_query(memories, "今天天气怎么样") == []


def test_anonymous_user_never_extracts_or_saves():
    class FakeRepo:
        def __init__(self):
            self.upserts = []

        async def upsert(self, **_kwargs):
            self.upserts.append(_kwargs)

    class FakeModel:
        def __init__(self):
            self.calls = 0

        def invoke(self, _messages):
            self.calls += 1
            return "[]"

    repo = FakeRepo()
    model = FakeModel()
    service = MemoryService.__new__(MemoryService)
    service.repository = repo
    service.model = model
    service.prompt = ""
    service.threshold = 0.8

    asyncio.run(
        service.extract_and_save(
            user_id="anonymous",
            user_message="我平时穿L码",
            source_message=None,
        )
    )

    assert model.calls == 0
    assert repo.upserts == []


def test_extract_and_save_skips_low_confidence():
    class FakeRepo:
        def __init__(self):
            self.upserts = []

        async def upsert(self, **_kwargs):
            self.upserts.append(_kwargs)

    class FakeModel:
        def invoke(self, _messages):
            return '[{"memory_key":"size","content":"常用尺码 L","confidence":0.5}]'

    repo = FakeRepo()
    service = MemoryService.__new__(MemoryService)
    service.repository = repo
    service.model = FakeModel()
    service.prompt = ""
    service.threshold = 0.8

    asyncio.run(
        service.extract_and_save(
            user_id="user-1",
            user_message="我平时穿L码",
            source_message=None,
        )
    )

    assert repo.upserts == []
