import asyncio
import os, uuid, hashlib
from fastapi import APIRouter, File, HTTPException, UploadFile, Depends

from sqlalchemy.ext.asyncio import AsyncSession
from db.session import get_db
from rag.vector_store import VectorStoreService
from core.config import pg_conf
from core.paths import get_abs_path
from core.validators import validate_file_extension
from db.file_repo import FileRepository

router = APIRouter(prefix="/api/files", tags=["Files"])

@router.post("/upload")
async def upload_and_split(
        file: UploadFile = File(...),
        chunk_size: int = pg_conf["chunk_size"],
        chunk_overlap: int = pg_conf["chunk_overlap"],
        db: AsyncSession = Depends(get_db),
):
    filename = file.filename or ""
    if not filename:
        raise HTTPException(status_code=400, detail="未检测到上传文件名")

    allowed_types = {t.lower().lstrip(".") for t in pg_conf.get("allow_knowledge_file_type", [])}
    try:
        extension = validate_file_extension(filename, allowed_types)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    temp_path = ""
    vs = VectorStoreService(chunk_size, chunk_overlap)
    try:
        data_dir = get_abs_path(pg_conf["data_path"])
        os.makedirs(data_dir, exist_ok=True)

        file_id = uuid.uuid4().hex
        saved_filename = f"{file_id}.{extension}"
        temp_path = os.path.join(data_dir, saved_filename)

        md5_hash = hashlib.md5()
        file_size = 0
        with open(temp_path, "wb") as f:
            while chunk := await file.read(8192):
                f.write(chunk)
                md5_hash.update(chunk)
                file_size += len(chunk)

        if file_size == 0:
            raise HTTPException(status_code=400, detail="上传文件为空")

        file_md5_hex = md5_hash.hexdigest()

        repo = FileRepository(db)
        exist_file = await repo.get_by_md5(md5_hex=file_md5_hex)
        if exist_file is not None:
            raise HTTPException(status_code=400, detail="文件已存在于向量库中！")

        # 向量写入（同步 PGVector，走线程池避免阻塞事件循环）
        added_ids = await asyncio.to_thread(vs.load_document, file_id, target_path=temp_path)
        if added_ids is None:
            raise HTTPException(status_code=500, detail="文件解析、切分并写入向量库失败")

        # 记录元数据；失败时补偿删除刚写入的向量（跨存储无法原子，补偿 + 对账脚本兜底）
        try:
            newfile = await repo.save(
                file_id=file_id,
                filename=filename,
                md5_hex=file_md5_hex,
                file_size=file_size // 1024,
            )
        except Exception:
            await asyncio.to_thread(vs.delete_documents, added_ids)
            raise

        return {
            "message": "文件解析、切分并写入向量库成功",
            "filename": filename,
            "chunks": added_ids,
            "file_id": newfile.id
        }
    except HTTPException:
        raise
    finally:
        await file.close()
        if temp_path and os.path.exists(temp_path):
            os.remove(temp_path)


@router.get("/list")
async def list_uploaded_files(db: AsyncSession = Depends(get_db)):
    repo = FileRepository(db)
    files = await repo.list_all()
    return {"files": files}


@router.delete("/{file_id}")
async def delete_uploaded_file(file_id: str, db: AsyncSession = Depends(get_db)):
    repo = FileRepository(db)

    # 先删主记录（不存在则 404，不动向量）；向量删除与记录删除在同一事务，任一步失败整体回滚
    deleted = await repo.delete_by_id(file_id=file_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="文件记录不存在")

    await repo.delete_vector_embeddings(file_id=file_id.replace("-", ""))
    return {"message": "文件记录已删除"}
