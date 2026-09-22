import inspect
from pathlib import Path

from db.repositories.conversation import SqlAlchemyConversationRepository
from db.repositories.file import SqlAlchemyFileRepository
from db.repositories.memory import SqlAlchemyMemoryRepository
from db.repositories.topic import SqlAlchemyTopicRepository


def test_repository_implementations_expose_required_methods():
    assert inspect.iscoroutinefunction(SqlAlchemyConversationRepository.add_turn)
    assert inspect.iscoroutinefunction(SqlAlchemyConversationRepository.get_recent_topic_messages)
    assert inspect.iscoroutinefunction(SqlAlchemyTopicRepository.switch)
    assert inspect.iscoroutinefunction(SqlAlchemyMemoryRepository.upsert)
    assert inspect.iscoroutinefunction(SqlAlchemyFileRepository.list_all)


def test_repositories_never_commit():
    root = Path(__file__).resolve().parents[1] / "db" / "repositories"
    for path in root.glob("*.py"):
        assert ".commit(" not in path.read_text(encoding="utf-8")
