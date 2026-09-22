"""数据库连接串 URL 编码测试。"""
from core.config import env_conf
from db.engine import build_async_db_url
from rag.vector_store import build_vector_db_url


def _patch_db_env(monkeypatch):
    monkeypatch.setattr(env_conf, "DB_USER", "dbuser")
    monkeypatch.setattr(env_conf, "DB_PASSWORD", "p@ss:w/rd")
    monkeypatch.setattr(env_conf, "DB_HOST", "db.example.com")
    monkeypatch.setattr(env_conf, "DB_PORT", 5432)
    monkeypatch.setattr(env_conf, "DB_NAME", "vectordb")


def test_async_db_url_encodes_password(monkeypatch):
    _patch_db_env(monkeypatch)
    dsn = build_async_db_url().render_as_string(hide_password=False)
    assert dsn.startswith("postgresql+asyncpg://")
    assert "p%40ss%3Aw%2Frd" in dsn
    assert "@" not in dsn.split("//")[1].split("@")[0].replace("%40", "")


def test_vector_db_url_encodes_password(monkeypatch):
    _patch_db_env(monkeypatch)
    dsn = build_vector_db_url()
    assert dsn.startswith("postgresql+psycopg://")
    assert "p%40ss%3Aw%2Frd" in dsn
