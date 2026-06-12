import uuid
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException
from rag.vector_store import VectorStoreService
from db.file_repo import FileRepository
from core.validators import validate_file_extension
from core.config import pg_conf


class DocumentService:
    def __init__(self, db: AsyncSession, chunk_size: int, chunk_overlap: int):
        self.repo = FileRepository(db)
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    async def upload(self, filename: str, temp_path: str, file_size: int, file_bytes: bytes) -> dict:
        import hashlib
        md5_hash = hashlib.md5()
        md5_hash.update(file_bytes)
        file_md5_hex = md5_hash.hexdigest()

        exist_file = await self.repo.get_by_md5(md5_hex=file_md5_hex)
        if exist_file is not None:
            raise HTTPException(status_code=400, detail="文件已存在于向量库中！")

        file_id = uuid.uuid4().hex
        split_documents = VectorStoreService(
            self.chunk_size, self.chunk_overlap
        ).load_document(file_id, target_path=temp_path)

        if split_documents is None:
            raise HTTPException(status_code=500, detail="文件解析、切分并写入向量库失败")

        newfile = await self.repo.save(
            file_id=file_id,
            filename=filename,
            md5_hex=file_md5_hex,
            file_size=file_size // 1024,
        )

        return {
            "filename": filename,
            "chunks": split_documents,
            "file_id": newfile.id,
        }
