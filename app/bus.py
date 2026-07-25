"""持久化日志与 SSE 总线。

每条事件追加写入 data/logs/system.jsonl；内存仅保留近期事件供管理页实时展示。
"""
import json
import queue
import threading
import time
from collections import deque
from datetime import datetime
from pathlib import Path

# 每个前端连接一个 Queue，broadcast 时逐个 put。
_subscribers: list[queue.Queue] = []
_lock = threading.Lock()
# 磁盘日志长期保留，内存只缓存最近日志，避免服务运行越久占用越大。
_HISTORY_MAX = 300
_history: deque[dict] = deque(maxlen=_HISTORY_MAX)
_LOG_DIR = Path(__file__).resolve().parents[1] / "data" / "logs"
LOG_FILE = _LOG_DIR / "system.jsonl"


def _load_recent_history() -> None:
    """启动时从持久化文件恢复最近记录，损坏的单行会被忽略。"""
    if not LOG_FILE.exists():
        return
    try:
        with LOG_FILE.open("r", encoding="utf-8") as handle:
            lines = deque(handle, maxlen=_HISTORY_MAX)
        for line in lines:
            try:
                evt = json.loads(line)
                if isinstance(evt, dict):
                    _history.append(evt)
            except (json.JSONDecodeError, TypeError):
                continue
    except OSError:
        pass


_load_recent_history()


def subscribe() -> queue.Queue:
    q: queue.Queue = queue.Queue(maxsize=500)
    with _lock:
        _subscribers.append(q)
    return q


def unsubscribe(q: queue.Queue) -> None:
    with _lock:
        if q in _subscribers:
            _subscribers.remove(q)


def log(message: str, channel: str = "system", level: str = "info") -> None:
    """持久化并广播日志；调用失败不会影响主业务。"""
    now = datetime.now().astimezone()
    evt = {
        "time": now.strftime("%Y-%m-%d %H:%M:%S"),
        "timestamp": now.isoformat(timespec="seconds"),
        "channel": channel,
        "level": level,
        "message": str(message),
    }
    with _lock:
        _history.append(evt)
        try:
            _LOG_DIR.mkdir(parents=True, exist_ok=True)
            with LOG_FILE.open("a", encoding="utf-8", newline="\n") as handle:
                handle.write(json.dumps(evt, ensure_ascii=False) + "\n")
        except OSError:
            pass
        subs = list(_subscribers)
    for q in subs:
        try:
            q.put_nowait(evt)
        except queue.Full:
            pass


def history() -> list[dict]:
    with _lock:
        return list(_history)


def event_stream(q: queue.Queue):
    """生成 SSE 数据流。首帧补发历史，之后阻塞等待新事件，定期发心跳防超时。"""
    for evt in history():
        yield f"data: {json.dumps(evt, ensure_ascii=False)}\n\n"
    while True:
        try:
            evt = q.get(timeout=15)
            yield f"data: {json.dumps(evt, ensure_ascii=False)}\n\n"
        except queue.Empty:
            yield f": keepalive {int(time.time())}\n\n"
