from fastapi import APIRouter, File, HTTPException, UploadFile
import os, uuid
from rag.vector_store import VectorStoreService
from utils.config_handler import pg_conf
from utils.path_tool import get_abs_path

router = APIRouter(prefix="/api/files", tags=["Files"])

@router.post("/upload")
async def upload_and_split(
        file: UploadFile = File(...),
        chunk_size: int = pg_conf["chunk_size"],
        chunk_overlap: int = pg_conf["chunk_overlap"]
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

        # 创建向量库服务实例
        vector_service = VectorStoreService(chunk_size, chunk_overlap)
        split_documents = vector_service.load_document()

        if split_documents is None:
            return {"message": "文件已存在于向量库中！"}

        return {


            "message": "文件解析、切分并写入向量库成功",
            "filename": filename,
            "chunks": split_documents
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"文件处理失败: {str(e)}")
    finally:
        await file.close()
        if temp_path and os.path.exists(temp_path):
            os.remove(temp_path)
