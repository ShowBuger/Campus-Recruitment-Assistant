"""FastAPI 入口：注册看板/状态/配置 router + 挂载 static SPA。

启动：uvicorn app.main:app --host 0.0.0.0 --port 8765
"""
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app import bus
from app.routers import dashboard, status, config, resume, ai, auth, admin, chat, progress_tracker, recommendations
from app.version import APP_VERSION

# Start background sync scheduler
dashboard.start_sync_scheduler()
progress_tracker.start_scheduler()

STATIC_DIR = os.path.join(os.path.dirname(__file__), "..", "static")
PROJECT_DIR = os.path.join(os.path.dirname(__file__), "..")
WWW_DIST = "/var/www/campus-dashboard/dist"  # nginx 静态文件目录


@asynccontextmanager
async def lifespan(app: FastAPI):
    bus.log(f"校招信息看板已启动 · PID {os.getpid()}", channel="system", level="success")
    try:
        yield
    finally:
        bus.log(f"校招信息看板已停止 · PID {os.getpid()}", channel="system", level="info")


app = FastAPI(title="校招信息看板", version=APP_VERSION, lifespan=lifespan)
app.add_middleware(GZipMiddleware, minimum_size=800, compresslevel=6)

# CORS for browser extension
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(admin.router)
app.include_router(dashboard.router)
app.include_router(status.router)
app.include_router(config.router)
app.include_router(resume.router)
app.include_router(ai.router)
app.include_router(recommendations.router)
app.include_router(chat.router)
app.include_router(progress_tracker.router)


def _dist_index():
    """返回 dist/index.html 的路径，优先从 www 目录读取（与 nginx 保持一致）。"""
    path = os.path.join(WWW_DIST, "index.html")
    if os.path.isfile(path):
        return path
    path = os.path.join(STATIC_DIR, "dist", "index.html")
    if os.path.isfile(path):
        return path
    return None

@app.get("/")
def index():
    di = _dist_index()
    if di:
        return FileResponse(di, headers={"Cache-Control": "no-cache"})
    return FileResponse(os.path.join(STATIC_DIR, "index.html"), headers={"Cache-Control": "no-cache"})


@app.get("/guide")
def guide():
    return FileResponse(
        os.path.join(STATIC_DIR, "docs.html"),
        media_type="text/html",
        headers={"Cache-Control": "no-cache"},
    )


# Vue SPA（开发/预览用，访问 /vue）
@app.get("/vue")
def vue_spa():
    di = _dist_index()
    if di:
        return FileResponse(di, headers={"Cache-Control": "no-cache"})
    raise HTTPException(status_code=404, detail="Vue 前端未构建，请运行 cd frontend && npm run build")


# ---- 静态资源 & Vue 构建产物 ----
# 必须在 SPA 回退路由之前挂载，否则 catch-all 会拦截所有 /dist/ 和 /static/ 请求
if os.path.isdir(STATIC_DIR):
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
if os.path.isdir(os.path.join(PROJECT_DIR, "assets")):
    app.mount("/assets", StaticFiles(directory=os.path.join(PROJECT_DIR, "assets")), name="assets")

_DIST_DIR = os.path.join(PROJECT_DIR, "static", "dist")
if os.path.isdir(_DIST_DIR):
    app.mount("/dist", StaticFiles(directory=_DIST_DIR), name="vue-dist")


# SPA 回退路由：支持 Vue Router history 模式下直接访问 /board、/records 等路径
# 注意：此路由必须放在 StaticFiles mount 之后，Starlette 按注册顺序匹配
@app.get("/{full_path:path}")
async def spa_fallback(full_path: str):
    # 排除 API 路径（API 路由在上面已注册，这里兜底返回 404）
    if full_path.startswith("api/"):
        raise HTTPException(status_code=404)
    # static/ dist/ assets/ 已被 StaticFiles mount 处理，不会到达这里
    # guide 有独立路由
    if full_path.startswith("guide"):
        raise HTTPException(status_code=404)
    di = _dist_index()
    if di:
        return FileResponse(di, headers={"Cache-Control": "no-cache"})
    raise HTTPException(status_code=404)
