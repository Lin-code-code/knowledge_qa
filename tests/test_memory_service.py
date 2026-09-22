"""长期偏好按意图筛选与匿名保护测试。"""
import asyncio
from datetime import datetime, timezone
from uuid import uuid4

from domain.decisions import MemoryCandidate
from domain.entities import MemoryItem
from services.memory_service import MemoryService


def _memory(key, content):
    now = datetime.now(timezone.utc)
    return MemoryItem(
        id=uuid4(),
        user_id="u1",
        memory_type="preference",
        memory_key=key,
        content=content,
        source_message_id=None,
        confidence=0.95,
        expires_at=None,
        status="active",
        created_at=now,
        updated_at=now,
    )


class FakeMemoryRepo:
    def __init__(self):
        self.upserts = []

    async def list_active(self, user_id, limit=12):
        return []

    async def upsert(self, **kwargs):
        self.upserts.append(kwargs)


class FakeExtractor:
    def __init__(self, candidates=()):
        self.candidates = list(candidates)
        self.calls = 0

    def extract(self, _user_message):
        self.calls += 1
        return self.candidates


def _service():
    return MemoryService(FakeMemoryRepo())


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
    repo = FakeMemoryRepo()
    extractor = FakeExtractor()
    service = MemoryService(repo, extractor)

    asyncio.run(
        service.extract_and_save(
            user_id="anonymous",
            user_message="我平时穿L码",
            source_message=None,
        )
    )

    assert extractor.calls == 0
    assert repo.upserts == []


def test_extract_and_save_skips_low_confidence():
    repo = FakeMemoryRepo()
    extractor = FakeExtractor(
        [MemoryCandidate(memory_key="size", content="常用尺码 L", confidence=0.5)]
    )
    service = MemoryService(repo, extractor)

    asyncio.run(
        service.extract_and_save(
            user_id="user-1",
            user_message="我平时穿L码",
            source_message=None,
        )
    )

    assert repo.upserts == []
