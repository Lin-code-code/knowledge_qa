from api.dependencies import get_chat_service, get_conversation_service
from db.session import get_db
from fastapi import FastAPI
from fastapi.testclient import TestClient


def test_dependencies_are_fastapi_callables():
    assert callable(get_chat_service)
    assert callable(get_conversation_service)


def test_app_import_registers_routes():
    from main import app
    paths = {route.path for route in app.routes}
    assert "/api/chat/" in paths
    assert "/api/conversations" in paths
