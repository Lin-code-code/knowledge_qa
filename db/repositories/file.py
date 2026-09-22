"""上传文件元数据的 SQLAlchemy 仓储实现。

事务边界由 ``db/session.py:get_db`` 统一管理，仓储只做 ``flush()``/``refresh()``，
不调用 ``commit()``。所有公开返回值均为 ``domain.entities`` 领域对象。
"""

from uuid import UUID

from sqlalchemy import delete, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from db.mappers import to_file_summary, to_uploaded_file
from db.models.uploaded_file import UploadedFile as UploadedFileModel
from domain.entities import FileSummary, UploadedFile


class SqlAlchemyFileRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_md5(self, md5_hex: str) -> UploadedFile | None:
        stmt = select(UploadedFileModel).where(UploadedFileModel.md5_hex == md5_hex)
        result = await self.session.execute(stmt)
        row = result.scalars().first()
        return to_uploaded_file(row) if row else None

    async def save(self, file_id: UUID, filename: str, md5_hex: str, file_size: int) -> UploadedFile:
        row = UploadedFileModel(id=file_id, filename=filename, md5_hex=md5_hex, size=file_size)
        self.session.add(row)
        await self.session.flush()
        await self.session.refresh(row)
        return to_uploaded_file(row)

    async def list_all(self) -> list[FileSummary]:
        # 应用表存带连字符 UUID，langchain 元数据存无连字符 UUID，故需 REPLACE 后关联
        sql_query = text("""
            SELECT
                uf.id,
                uf.filename,
                uf.size,
                COUNT(*) AS chunks
            FROM uploaded_files uf
            JOIN langchain_pg_embedding lpe
                ON (REPLACE(uf.id::TEXT, '-', '')) = (lpe.cmetadata ->> 'file_id')
            WHERE lpe.cmetadata ? 'file_id'
            GROUP BY uf.id, uf.filename, uf.size
            ORDER BY chunks DESC
        """)
        result = await self.session.execute(sql_query)
        return [to_file_summary(row) for row in result.mappings().all()]

    async def delete_by_id(self, file_id: UUID) -> bool:
        stmt = delete(UploadedFileModel).where(UploadedFileModel.id == file_id).returning(UploadedFileModel.id)
        result = await self.session.execute(stmt)
        deleted_id = result.scalar_one_or_none()
        return deleted_id is not None

    async def delete_index_records(self, file_id: str) -> int:
        sql_query = text(
            "DELETE FROM langchain_pg_embedding WHERE cmetadata ->> 'file_id' = :fid"
        )
        res = await self.session.execute(sql_query, {"fid": file_id})
        return res.rowcount
