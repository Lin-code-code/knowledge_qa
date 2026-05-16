from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from routers import files

app = FastAPI(
    title="知识库问答系统",
    version="0.1.1"
)


# 挂载路由
app.include_router(files.router)

