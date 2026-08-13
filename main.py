import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from api import chat, documents
from core.logger import logger
from db.session import close_db


static_dir = os.path.join(os.path.dirname(__file__), "static")


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    await close_db()


app = FastAPI(
    title="知识库问答系统",
    version="0.2.0",
    lifespan=lifespan,
)

if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

app.include_router(documents.router)
app.include_router(chat.router)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    logger.warning(f"[validation] {request.method} {request.url.path} 参数校验失败: {exc.errors()}")
    return JSONResponse(status_code=422, content={"detail": "请求参数不合法，请检查输入"})


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    # 完整堆栈进 logs/，对外只返回通用文案，避免泄露内部错误细节
    logger.exception(f"[unhandled] {request.method} {request.url.path}", exc_info=exc)
    return JSONResponse(status_code=500, content={"detail": "服务器内部错误，请稍后重试"})


@app.get("/")
async def root():
    index_path = os.path.join(static_dir, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return {"message": "前端页面未找到，请检查 static/index.html"}
