"""上传文件的领域应用服务。

逐段迁移旧 ``api/documents.py`` 的业务流程：校验扩展名 → 流式落盘并算 MD5 →
按 MD5 去重 → 写入向量库 → 保存元数据；向量写入成功但元数据保存失败时补偿删除刚写入的向量
（跨存储无法原子，补偿 + 对账脚本兜底）。

本模块只依赖 ``core.*`` 与 ``domain.*``，不导入 ``db`` / ``api`` / ``rag`` / FastAPI。
"""

import asyncio
import hashlib
from dataclasses import dataclass
from pathlib import Path
from uuid import UUID, uuid4

from core.config import pg_conf
from core.paths import get_abs_path
from core.validators import validate_file_extension
from domain.entities import FileSummary, UploadedFile
from domain.errors import (
    DocumentIndexError,
    DocumentNotFoundError,
    DuplicateDocumentError,
    EmptyDocumentError,
    UnsupportedDocumentTypeError,
)
from domain.ports import AsyncDocumentReader, DocumentIndexPort, FileRepositoryPort


@dataclass(slots=True)
class DocumentUploadResult:
    file: UploadedFile
    chunks: list[str]


class DocumentService:
    def __init__(
        self,
        files: FileRepositoryPort,
        index: DocumentIndexPort,
        *,
        data_dir: str | None = None,
        allowed_types: set[str] | None = None,
    ):
        self.files = files
        self.index = index
        self.data_dir = data_dir or get_abs_path(pg_conf["data_path"])
        self.allowed_types = allowed_types or {
            item.lower().lstrip(".") for item in pg_conf.get("allow_knowledge_file_type", [])
        }

    async def upload(self, filename: str, stream: AsyncDocumentReader) -> DocumentUploadResult:
        if not filename:
            raise UnsupportedDocumentTypeError("未检测到上传文件名")
        try:
            extension = validate_file_extension(filename, self.allowed_types)
        except ValueError as exc:
            raise UnsupportedDocumentTypeError(str(exc)) from exc

        data_dir = Path(self.data_dir)
        data_dir.mkdir(parents=True, exist_ok=True)
        file_id = uuid4()
        index_file_id = file_id.hex
        temp_path = data_dir / f"{index_file_id}.{extension}"
        md5_hash = hashlib.md5()
        file_size = 0
        added_ids: list[str] = []
        try:
            with temp_path.open("wb") as target:
                while chunk := await stream.read(8192):
                    target.write(chunk)
                    md5_hash.update(chunk)
                    file_size += len(chunk)

            if file_size == 0:
                raise EmptyDocumentError("上传文件为空")

            file_md5_hex = md5_hash.hexdigest()
            if await self.files.get_by_md5(file_md5_hex) is not None:
                raise DuplicateDocumentError("文件已存在于向量库中！")

            added_ids = await asyncio.to_thread(
                self.index.load_document,
                index_file_id,
                str(temp_path),
            )
            if not added_ids:
                raise DocumentIndexError("文件解析、切分并写入向量库失败")

            try:
                item = await self.files.save(
                    file_id=file_id,
                    filename=filename,
                    md5_hex=file_md5_hex,
                    file_size=file_size // 1024,
                )
            except Exception:
                await asyncio.to_thread(self.index.delete_documents, added_ids)
                raise
            return DocumentUploadResult(file=item, chunks=added_ids)
        finally:
            if temp_path.exists():
                temp_path.unlink()

    async def list_all(self) -> list[FileSummary]:
        return await self.files.list_all()

    async def delete(self, file_id: UUID) -> None:
        deleted = await self.files.delete_by_id(file_id)
        if not deleted:
            raise DocumentNotFoundError(str(file_id))
        await self.files.delete_index_records(file_id.hex)
