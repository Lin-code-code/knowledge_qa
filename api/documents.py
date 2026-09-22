from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile

from api.dependencies import get_document_service, get_upload_document_service
from core.security import require_api_key
from domain.errors import (
    DocumentIndexError,
    DocumentNotFoundError,
    DuplicateDocumentError,
    EmptyDocumentError,
    UnsupportedDocumentTypeError,
)
from services.document_service import DocumentService

router = APIRouter(prefix="/api/files", tags=["Files"], dependencies=[Depends(require_api_key)])


@router.post("/upload")
async def upload_and_split(
    file: UploadFile = File(...),
    service: DocumentService = Depends(get_upload_document_service),
):
    try:
        result = await service.upload(file.filename or "", file)
    except UnsupportedDocumentTypeError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except EmptyDocumentError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except DuplicateDocumentError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except DocumentIndexError as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    finally:
        await file.close()

    return {
        "message": "文件解析、切分并写入向量库成功",
        "filename": result.file.filename,
        "chunks": result.chunks,
        "file_id": str(result.file.id),
    }


@router.get("/list")
async def list_uploaded_files(service: DocumentService = Depends(get_document_service)):
    files = await service.list_all()
    return {"files": files}


@router.delete("/{file_id}")
async def delete_uploaded_file(
    file_id: str,
    service: DocumentService = Depends(get_document_service),
):
    # file_id 保持 str 类型以维持 OpenAPI 契约；非法 UUID 由 UUID() 抛出 ValueError，
    # 经 main.py 全局异常处理器返回 500，与旧实现（裸串直达 SQLAlchemy/asyncpg）行为一致。
    try:
        await service.delete(UUID(file_id))
    except DocumentNotFoundError:
        raise HTTPException(status_code=404, detail="文件记录不存在")
    return {"message": "文件记录已删除"}
