from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from routers import files, chat
import os

app = FastAPI(
    title="知识库问答系统",
    version="0.1.1"
)

# 挂载静态文件目录
static_dir = os.path.join(os.path.dirname(__file__), "static")
if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

# 挂载路由
app.include_router(files.router)
app.include_router(chat.router)

# 根路径返回前端页面
@app.get("/")
async def root():
    index_path = os.path.join(static_dir, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return {"message": "前端页面未找到，请检查 static/index.html"}

