"""_state 全局状态：per-user 后台任务 & 数据缓存。"""
import threading
import time

_lock = threading.Lock()

# 全局共享状态
_global_state = {
    "scanning": False,
    "last_scan": None,
    "started_at": time.time(),
}

# per-user 缓存: {user_id: {cache, cache_at}}
_user_caches: dict[int, dict] = {}


def get() -> dict:
    with _lock:
        return dict(_global_state)


def update(**kwargs) -> None:
    with _lock:
        _global_state.update(kwargs)


def set_cache(user_id: int, data) -> None:
    with _lock:
        _user_caches[user_id] = {
            "cache": data,
            "cache_at": time.time(),
        }


def get_cache(user_id: int, max_age: float = 30.0):
    with _lock:
        entry = _user_caches.get(user_id)
        if entry and (time.time() - entry["cache_at"]) < max_age:
            return entry["cache"]
    return None
