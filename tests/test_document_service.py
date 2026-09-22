import asyncio
from datetime import datetime, timezone
from uuid import UUID, uuid4

from domain.entities import FileSummary, UploadedFile
from domain.errors import DuplicateDocumentError
from services.document_service import DocumentService


class Stream:
    def __init__(self, chunks):
        self.chunks = list(chunks)

    async def read(self, size):
        return self.chunks.pop(0) if self.chunks else b""


class FakeFileRepo:
    def __init__(self):
        self.saved = []

    async def get_by_md5(self, md5_hex):
        return None

    async def save(self, file_id, filename, md5_hex, file_size):
        now = datetime.now(timezone.utc)
        item = UploadedFile(file_id, filename, md5_hex, file_size, now)
        self.saved.append(item)
        return item

    async def list_all(self):
        return [FileSummary(uuid4(), "a.txt", 1, 2)]

    async def delete_by_id(self, file_id):
        return True

    async def delete_index_records(self, file_id):
        return 2


class FakeIndex:
    def __init__(self):
        self.deleted = []

    def load_document(self, file_id, target_path):
        return [f"{file_id}-chunk0"]

    def delete_documents(self, ids):
        self.deleted.extend(ids)


def test_document_service_uploads_and_returns_chunks(tmp_path, monkeypatch):
    async def scenario():
        repo = FakeFileRepo()
        index = FakeIndex()
        service = DocumentService(repo, index, data_dir=str(tmp_path), allowed_types={"txt"})
        result = await service.upload("a.txt", Stream([b"hello"]))
        assert result.file.filename == "a.txt"
        assert result.chunks == [f"{result.file.id.hex}-chunk0"]
    asyncio.run(scenario())
