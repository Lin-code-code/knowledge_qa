"""API Key 鉴权依赖测试。"""
import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

import core.security as security_module
from core.security import require_api_key


def _make_client() -> TestClient:
    app = FastAPI()

    @app.get("/ping", dependencies=[Depends(require_api_key)])
    def ping():
        return {"ok": True}

    return TestClient(app)


def test_auth_disabled_when_no_keys_configured(monkeypatch):
    """未配置 API_KEYS 时放行，保证本地开发/存量部署不受影响。"""
    monkeypatch.setattr(security_module.env_conf, "API_KEYS", "")
    client = _make_client()
    resp = client.get("/ping")
    assert resp.status_code == 200


def test_auth_rejects_missing_and_wrong_key(monkeypatch):
    monkeypatch.setattr(security_module.env_conf, "API_KEYS", "key-a,key-b")
    client = _make_client()

    missing = client.get("/ping")
    assert missing.status_code == 401

    wrong = client.get("/ping", headers={"X-API-Key": "key-c"})
    assert wrong.status_code == 401


def test_auth_accepts_configured_key(monkeypatch):
    monkeypatch.setattr(security_module.env_conf, "API_KEYS", "key-a,key-b")
    client = _make_client()

    resp = client.get("/ping", headers={"X-API-Key": "key-b"})
    assert resp.status_code == 200
    assert resp.json() == {"ok": True}
