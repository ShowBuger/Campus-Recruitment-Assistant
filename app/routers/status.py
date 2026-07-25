"""状态接口：GET /api/status 返回 _state 快照，前端轮询。GET /api/stream 是 SSE 日志流。"""
from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from app import bus, state
from app.version import APP_VERSION

router = APIRouter(prefix="/api", tags=["status"])


@router.get("/version")
def get_version():
    return {"version": APP_VERSION}


@router.get("/status")
def get_status():
    return state.get()


@router.get("/stream")
def stream():
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
def logs_history():
    return {"logs": bus.history()}
