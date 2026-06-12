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

        split_documents = VectorStoreService(chunk_size, chunk_overlap).load_document(file_id, target_path=temp_path)
        if split_documents is None:
            raise HTTPException(status_code=500, detail="文件解析、切分并写入向量库失败")

        newfile = await repo.save(
            file_id=file_id,
            filename=filename,
            md5_hex=file_md5_hex,
            file_size=file_size // 1024,
        )

        return {
            "message": "文件解析、切分并写入向量库成功",
            "filename": filename,
            "chunks": split_documents,
            "file_id": newfile.id
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"文件处理失败: {str(e)}")
    finally:
        await file.close()
        if temp_path and os.path.exists(temp_path):
            os.remove(temp_path)


@router.get("/list")
async def list_uploaded_files(db: AsyncSession = Depends(get_db)):
    try:
        repo = FileRepository(db)
        files = await repo.list_all()
        return {"files": files}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取文件列表失败: {str(e)}")


@router.delete("/{file_id}")
async def delete_uploaded_file(file_id: str, db: AsyncSession = Depends(get_db)):
    try:
        repo = FileRepository(db)
        deleted = await repo.delete_by_id(file_id=file_id)
        deleted_count = await repo.delete_vector_embeddings(file_id=file_id.replace("-", ""))
        if not deleted:
            raise HTTPException(status_code=404, detail="文件记录不存在")
        return {"message": f"文件记录已删除"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"删除文件记录失败: {str(e)}")
