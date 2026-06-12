from typing import Sequence, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete, text
from models.uploaded_file import UploadedFile


class FileRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_md5(self, md5_hex: str) -> UploadedFile | None:
        stmt = select(UploadedFile).where(UploadedFile.md5_hex == md5_hex)
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def save(self, file_id: str, filename: str, md5_hex: str, file_size: int) -> UploadedFile:
        new_file = UploadedFile(id=file_id, filename=filename, md5_hex=md5_hex, size=file_size)
        self.session.add(new_file)
        await self.session.commit()
        await self.session.refresh(new_file)
        return new_file

    async def list_all(self) -> Sequence[UploadedFile]:
        stmt = select(UploadedFile).order_by(UploadedFile.uploaded_at.desc())
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def delete_by_id(self, file_id: str) -> bool:
        stmt = delete(UploadedFile).where(UploadedFile.id == file_id).returning(UploadedFile.id)
        result = await self.session.execute(stmt)
        deleted_id = result.scalar_one_or_none()
        await self.session.commit()
        return deleted_id is not None

    async def delete_vector_embeddings(self, file_id: str) -> int:
        sql_query = text(
            "DELETE FROM langchain_pg_embedding WHERE cmetadata ->> 'file_id' = :fid"
        )
        res = await self.session.execute(sql_query, {"fid": file_id})
        await self.session.commit()
        return res.rowcount
