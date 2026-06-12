from fastapi import APIRouter, File, HTTPException, UploadFile, Depends
import os, uuid

from history.db.engine import get_db
from rag.vector_store import VectorStoreService
from utils.config_handler import pg_conf
from utils.path_tool import get_abs_path

from utils.file_handler import get_file_md5_hex
from history.db.files import get_uploaded_file_by_md5, save_uploaded_file_details, get_all_uploaded_files, \
    delete_uploaded_file_by_id, delete_by_file_id

router = APIRouter(prefix="/api/files", tags=["Files"])

@router.post("/upload")
async def upload_and_split(
        file: UploadFile = File(...),
        chunk_size: int = pg_conf["chunk_size"],
        chunk_overlap: int = pg_conf["chunk_overlap"],
        db = Depends(get_db)
):
    filename = file.filename or ""
    if not filename:
        raise HTTPException(status_code=400, detail="未检测到上传文件名")

    allowed_types = {t.lower().lstrip(".") for t in pg_conf.get("allow_knowledge_file_type", [])}
    extension = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if extension not in allowed_types:
        raise HTTPException(
            status_code=400,
            detail=f"不支持的文件类型: {extension or 'unknown'}，仅支持: {sorted(allowed_types)}",
        )

    file_bytes = await file.read()
    if not file_bytes:
        raise HTTPException(status_code=400, detail="上传文件为空")

    temp_path = ""
    try:
        data_dir = get_abs_path(pg_conf["data_path"])
        os.makedirs(data_dir, exist_ok=True)

        # 用 uuid 防止并发上传时文件名冲突
        file_id = uuid.uuid4().hex
        saved_filename = f"{file_id}.{extension}"
        temp_path = os.path.join(data_dir, saved_filename)

        with open(temp_path, "wb") as f:
            f.write(file_bytes)

        file_md5_hex = get_file_md5_hex(temp_path)
        exist_file = await get_uploaded_file_by_md5(md5_hex=file_md5_hex, db=db)
        if exist_file is not None:
            raise HTTPException(status_code=400, detail="文件已存在于向量库中！")
        else:
            # 创建向量库服务实例，加载文件并切分存入向量库
            split_documents = VectorStoreService(chunk_size, chunk_overlap).load_document(file_id, target_path=temp_path)

        if split_documents is None:
            raise HTTPException(status_code=500, detail="文件解析、切分并写入向量库失败")

        # 保存上传文件的详情到数据库
        newfile = await save_uploaded_file_details(
            file_id=file_id,
            filename=filename,
            md5_hex=file_md5_hex,
            file_size=file.size // 1024,
            db=db
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
async def list_uploaded_files(db = Depends(get_db)):
    try:
        files = await get_all_uploaded_files(db=db)
        return {"files": files}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取文件列表失败: {str(e)}")


@router.delete("/{file_id}")
async def delete_uploaded_file(file_id: str, db = Depends(get_db)):
    try:
        # 先删除数据库中的文件记录
        deleted = await delete_uploaded_file_by_id(file_id=file_id, db=db)
        # print(file_id)
        # 删除向量库中的相关向量数据
        deleted_count = await delete_by_file_id(file_id=file_id.replace("-", ""), db=db)
        if not deleted:
            raise HTTPException(status_code=404, detail="文件记录不存在")
        return {"message": f"文件记录已删除"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"删除文件记录失败: {str(e)}")
