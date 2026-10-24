"""状态接口：GET /api/status 返回 _state 快照，前端轮询。GET /api/stream 是 SSE 日志流。"""
from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from app import auth as auth_module, bus, state
from app.version import APP_VERSION

router = APIRouter(prefix="/api", tags=["status"])


@router.get("/version")
def get_version():
    return {"version": APP_VERSION}


@router.get("/status")
def get_status():
    return state.get()


@router.get("/stream")
def stream(user: dict = Depends(auth_module.get_current_user)):
    # 管理员可见实时日志流
    if not (user.get("is_root") or user.get("is_admin")):
        from fastapi import HTTPException
        raise HTTPException(status_code=403, detail="仅管理员可以查看系统日志")
    q = bus.subscribe()

    def gen():
        try:
            yield from bus.event_stream(q)
        finally:
            bus.unsubscribe(q)

    return StreamingResponse(gen(), media_type="text/event-stream", headers={
        "Cache-Control": "no-cache",
        "X-Accel-Buffering": "no",
    })


@router.get("/logs/history")
def logs_history(user: dict = Depends(auth_module.get_current_user)):
    if not (user.get("is_root") or user.get("is_admin")):
        from fastapi import HTTPException
        raise HTTPException(status_code=403, detail="仅管理员可以查看系统日志")
    return {"logs": bus.history()}
