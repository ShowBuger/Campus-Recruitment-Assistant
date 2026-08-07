"""SQLite database backup, restore, and three-day retention scheduler."""
from __future__ import annotations

import sqlite3
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

from app import bus, database

BACKUP_DIR = database.DATA_DIR / "backups"
BACKUP_INTERVAL_SECONDS = 12 * 60 * 60
BACKUP_RETENTION_DAYS = 3
BACKUP_RETENTION_SECONDS = BACKUP_RETENTION_DAYS * 24 * 60 * 60
_scheduler_started = False
_operation_lock = threading.Lock()


def _backup_name(prefix: str = "auto") -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"{prefix}-{stamp}.db"


def _resolve_backup(name: str) -> Path:
    if not name or Path(name).name != name or not name.endswith(".db"):
        raise ValueError("备份文件名无效")
    path = (BACKUP_DIR / name).resolve()
    if path.parent != BACKUP_DIR.resolve():
        raise ValueError("备份文件名无效")
    return path


def create_backup(prefix: str = "manual") -> dict:
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    path = BACKUP_DIR / _backup_name(prefix)
    with _operation_lock:
        source = database.get_db()
        destination = sqlite3.connect(str(path))
        try:
            source.backup(destination)
        finally:
            destination.close()
    info = _backup_info(path)
    cleanup_expired_backups()
    return info


def _backup_info(path: Path) -> dict:
    stat = path.stat()
    created_at = datetime.fromtimestamp(stat.st_mtime, timezone.utc).isoformat()
    return {"name": path.name, "size": stat.st_size, "created_at": created_at}


def cleanup_expired_backups(now: float | None = None) -> list[str]:
    """Delete database snapshots older than the configured retention window."""
    if not BACKUP_DIR.exists():
        return []
    cutoff = (time.time() if now is None else now) - BACKUP_RETENTION_SECONDS
    deleted: list[str] = []
    with _operation_lock:
        for path in BACKUP_DIR.glob("*.db"):
            if not path.is_file() or path.stat().st_mtime >= cutoff:
                continue
            path.unlink()
            deleted.append(path.name)
    return deleted


def list_backups() -> list[dict]:
    if not BACKUP_DIR.exists():
        return []
    return sorted(
        (_backup_info(path) for path in BACKUP_DIR.glob("*.db") if path.is_file()),
        key=lambda item: item["created_at"],
        reverse=True,
    )


def delete_backup(name: str) -> None:
    path = _resolve_backup(name)
    if not path.is_file():
        raise FileNotFoundError(name)
    path.unlink()


def restore_backup(name: str) -> dict:
    path = _resolve_backup(name)
    if not path.is_file():
        raise FileNotFoundError(name)

    safety_backup = create_backup("before-restore")
    with _operation_lock:
        source = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
        destination = database.get_db()
        try:
            source.backup(destination)
        finally:
            source.close()
    return safety_backup


def _scheduler_loop() -> None:
    while True:
        try:
            deleted = cleanup_expired_backups()
            if deleted:
                bus.log(f"已清理 {len(deleted)} 个超过 {BACKUP_RETENTION_DAYS} 天的数据库备份", channel="system")
            backups = list_backups()
            latest = max(
                (datetime.fromisoformat(item["created_at"]).timestamp() for item in backups),
                default=0,
            )
            if time.time() - latest >= BACKUP_INTERVAL_SECONDS:
                info = create_backup("auto")
                bus.log(f"数据库自动备份完成 · {info['name']}", channel="system", level="success")
        except Exception as exc:
            bus.log(f"数据库自动备份失败 · {exc}", channel="system", level="error")
        time.sleep(5 * 60)


def start_scheduler() -> None:
    global _scheduler_started
    if _scheduler_started:
        return
    _scheduler_started = True
    threading.Thread(target=_scheduler_loop, daemon=True, name="database-backup").start()
