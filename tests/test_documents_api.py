"""`api/documents.py` 的对外契约守卫：上传路由的状态码映射与成功响应体。

用 ``app.dependency_overrides`` 注入假 ``DocumentService``，不连数据库、不碰向量库。
文案一律取异常自身 message 逐字断言，防止"改坏了还假绿"。
"""

from datetime import datetime, timezone
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from api.dependencies import get_upload_document_service
from domain.entities import UploadedFile
from domain.errors import (
    DocumentIndexError,
    DuplicateDocumentError,
    EmptyDocumentError,
    UnsupportedDocumentTypeError,
)
from main import app
from services.document_service import DocumentUploadResult


class FakeService:
    def __init__(self, result=None, error=None):
        self.result = result
        self.error = error

    async def upload(self, filename, stream):
        if self.error is not None:
            raise self.error
        return self.result


@pytest.fixture
def client():
    def make(service):
        app.dependency_overrides[get_upload_document_service] = lambda: service
        return TestClient(app, raise_server_exceptions=False)

    yield make
    app.dependency_overrides.clear()


@pytest.mark.parametrize(
    "error, expected_status",
    [
        (UnsupportedDocumentTypeError("未检测到上传文件名"), 400),
        (EmptyDocumentError("上传文件为空"), 400),
        (DuplicateDocumentError("文件已存在于向量库中！"), 400),
        (DocumentIndexError("文件解析、切分并写入向量库失败"), 500),
    ],
)
def test_upload_maps_domain_errors_to_status_and_message(client, error, expected_status):
    with client(FakeService(error=error)) as c:
        response = c.post("/api/files/upload", files={"file": ("a.txt", b"hello", "text/plain")})
    assert response.status_code == expected_status
    assert response.json() == {"detail": str(error)}


def test_upload_success_response_contract(client):
    file_id = uuid4()
    result = DocumentUploadResult(
        file=UploadedFile(file_id, "a.txt", "d41d8cd98f00b204e9800998ecf8427e", 1, datetime.now(timezone.utc)),
        chunks=[f"{file_id.hex}-chunk0"],
    )
    with client(FakeService(result=result)) as c:
        response = c.post("/api/files/upload", files={"file": ("a.txt", b"hello", "text/plain")})

    assert response.status_code == 200
    assert response.json() == {
        "message": "文件解析、切分并写入向量库成功",
        "filename": "a.txt",
        "chunks": [f"{file_id.hex}-chunk0"],
        "file_id": str(file_id),
    }
    body_file_id = response.json()["file_id"]
    assert UUID(body_file_id) == file_id
    assert len(body_file_id) == 36 and body_file_id.count("-") == 4
