"""FastAPI 入口：注册看板/状态/配置 router + 挂载 static SPA。

启动：uvicorn app.main:app --host 0.0.0.0 --port 8765
"""
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app import bus
from app.routers import dashboard, status, config, resume, ai, auth, admin, chat, autofill

# Start background sync scheduler
dashboard.start_sync_scheduler()

STATIC_DIR = os.path.join(os.path.dirname(__file__), "..", "static")
PROJECT_DIR = os.path.join(os.path.dirname(__file__), "..")


@asynccontextmanager
async def lifespan(app: FastAPI):
    bus.log("校招信息看板已启动", channel="system", level="success")
    yield


app = FastAPI(title="校招信息看板", version="0.5", lifespan=lifespan)

app.include_router(auth.router)
app.include_router(admin.router)
app.include_router(dashboard.router)
app.include_router(status.router)
app.include_router(config.router)
app.include_router(resume.router)
app.include_router(ai.router)
app.include_router(chat.router)
app.include_router(autofill.router)


@app.get("/")
def index():
    return FileResponse(os.path.join(STATIC_DIR, "index.html"))


# 静态资源
if os.path.isdir(STATIC_DIR):
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
if os.path.isdir(os.path.join(PROJECT_DIR, "assets")):
    app.mount("/assets", StaticFiles(directory=os.path.join(PROJECT_DIR, "assets")), name="assets")
