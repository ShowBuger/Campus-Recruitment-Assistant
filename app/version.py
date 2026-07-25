"""应用版本号：以项目根目录 VERSION 文件为唯一来源，供 FastAPI 元数据与 /api/version 共用。"""
import os

_VERSION_FILE = os.path.join(os.path.dirname(__file__), "..", "VERSION")


def _read_version() -> str:
    try:
        with open(_VERSION_FILE, encoding="utf-8") as f:
            return f.read().strip().lstrip("v") or "0.0"
    except OSError:
        return "0.0"


APP_VERSION = _read_version()
