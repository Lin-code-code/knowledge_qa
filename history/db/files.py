"""
    这里存放文件相关的数据库操作
"""
from typing import Sequence, Any

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete, text
from history.models import UploadedFile


# 查询是否已经上传过相同 md5 的文件，如果有就返回文件信息，没有就返回 None
async def get_uploaded_file_by_md5(
        md5_hex: str,
        db: AsyncSession
) -> UploadedFile | None:
    stmt = select(UploadedFile).where(UploadedFile.md5_hex == md5_hex)
    result = await db.execute(stmt)
    return result.scalars().first()


# 保存上传文件的信息到数据库
async def save_uploaded_file_details(
        file_id: str,
        filename: str,
        md5_hex: str,
        file_size: int,
        db: AsyncSession
) -> UploadedFile:
    new_file = UploadedFile(
        id=file_id,
        filename=filename,
        md5_hex=md5_hex,
        size=file_size
    )
    db.add(new_file)
    await db.commit()
    await db.refresh(new_file)
    return new_file


# 获取所有已上传文件的信息列表
async def get_all_uploaded_files(db: AsyncSession) -> Sequence[Any]:
    stmt = select(UploadedFile).order_by(UploadedFile.uploaded_at.desc())
    result = await db.execute(stmt)
    return result.scalars().all()


# 删除指定 id 的上传文件记录
async def delete_uploaded_file_by_id(
        file_id: str,
        db: AsyncSession
) -> bool:
    stmt = delete(UploadedFile).where(UploadedFile.id == file_id).returning(UploadedFile.id)
    result = await db.execute(stmt)
    deleted_id = result.scalar_one_or_none()
    await db.commit()
    return deleted_id is not None

# 通过 file_id 异步删除向量数据
async def delete_by_file_id(file_id: str, db: AsyncSession):
    try:
        # 操作langchain默认表，通过编写原生 SQL (使用 ->> 提取 JSONB 文本值)
        sql_query = text(
            "DELETE FROM langchain_pg_embedding WHERE cmetadata ->> 'file_id' = :fid"
        )
        # 执行删除
        res = await db.execute(sql_query, {"fid": file_id})
        # 提交事务
        await db.commit()
        return res.rowcount
    except Exception as e:
        # 发生错误时回滚
        await db.rollback()
        raise e