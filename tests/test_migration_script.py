"""迁移脚本关键步骤守护测试。

真实执行依赖 PostgreSQL，这里做静态断言防止后续误删关键迁移步骤。
"""
from pathlib import Path

MIGRATION_SQL = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "migrate_conversation_memory.sql"
)


def _sql() -> str:
    return MIGRATION_SQL.read_text(encoding="utf-8")


def test_migration_creates_tables_and_extends_messages():
    content = _sql()
    assert "CREATE EXTENSION IF NOT EXISTS pgcrypto" in content
    assert "CREATE TABLE IF NOT EXISTS conversation_topics" in content
    assert "CREATE TABLE IF NOT EXISTS memory_items" in content
    for column in ("topic_id", "turn_id", "intent", "scope_label", "is_refusal", "memory_eligible"):
        assert f"ADD COLUMN IF NOT EXISTS {column}" in content


def test_migration_enforces_one_active_topic():
    content = _sql()
    assert "uq_topics_one_active" in content
    assert "status = 'active'" in content


def test_migration_backfills_legacy_conversations():
    content = _sql()
    assert "INSERT INTO conversation_topics" in content
    assert "SET topic_id = t.id" in content
    assert "SET turn_id" in content


def test_migration_marks_legacy_refusals_as_not_memory_eligible():
    content = _sql()
    assert "is_refusal" in content
    assert "memory_eligible" in content
    assert "暂无法回答该问题" in content
