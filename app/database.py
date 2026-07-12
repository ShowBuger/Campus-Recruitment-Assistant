"""SQLite 数据库：用户账号、独立配置、本地日程持久化。"""
import sqlite3
import os
import threading
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / "data"
DB_PATH = DATA_DIR / "app.db"

# 写锁，防止并发写入冲突
_write_lock = threading.Lock()


def _ensure_dir() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)


def get_db() -> sqlite3.Connection:
    """获取数据库连接，自动初始化表结构。"""
    _ensure_dir()
    conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    _init_tables(conn)
    return conn


def _init_tables(conn: sqlite3.Connection) -> None:
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            created_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS user_configs (
            user_id INTEGER PRIMARY KEY,
            feishu_app_id TEXT DEFAULT '',
            feishu_app_secret TEXT DEFAULT '',
            feishu_app_token TEXT DEFAULT '',
            main_table_id TEXT DEFAULT '',
            deepseek_api_key TEXT DEFAULT '',
            deepseek_model TEXT DEFAULT 'deepseek-v4-flash',
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS local_events (
            id TEXT PRIMARY KEY,
            user_id INTEGER NOT NULL,
            date TEXT NOT NULL,
            label TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        );
    """)
    conn.commit()


# ── 用户管理 ────────────────────────────────────────

def create_user(username: str, password_hash: str) -> dict | None:
    with _write_lock:
        db = get_db()
        try:
            cur = db.execute(
                "INSERT INTO users (username, password_hash) VALUES (?, ?)",
                (username, password_hash),
            )
            db.commit()
            user_id = cur.lastrowid
            # 为新用户创建默认空配置
            db.execute("INSERT INTO user_configs (user_id) VALUES (?)", (user_id,))
            db.commit()
            return {"id": user_id, "username": username}
        except sqlite3.IntegrityError:
            return None  # 用户名已存在


def get_user_by_username(username: str) -> dict | None:
    db = get_db()
    row = db.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
    return dict(row) if row else None


def get_user_by_id(user_id: int) -> dict | None:
    db = get_db()
    row = db.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    return dict(row) if row else None


# ── 用户配置（独立 Feishu / DeepSeek 连接）──────────

def get_user_config(user_id: int) -> dict:
    db = get_db()
    row = db.execute(
        "SELECT * FROM user_configs WHERE user_id = ?", (user_id,)
    ).fetchone()
    if not row:
        db.execute("INSERT INTO user_configs (user_id) VALUES (?)", (user_id,))
        db.commit()
        return {
            "FEISHU_APP_ID": "",
            "FEISHU_APP_SECRET": "",
            "FEISHU_APP_TOKEN": "",
            "MAIN_TABLE_ID": "",
            "DEEPSEEK_API_KEY": "",
            "DEEPSEEK_MODEL": "deepseek-v4-flash",
            "configured": False,
        }
    d = dict(row)
    d.pop("user_id", None)
    d["configured"] = bool(
        d.get("feishu_app_id") and d.get("feishu_app_secret")
        and d.get("feishu_app_token") and d.get("main_table_id")
    )
    return d


def save_user_config(user_id: int, config: dict) -> None:
    with _write_lock:
        db = get_db()
        db.execute(
            """INSERT INTO user_configs (user_id, feishu_app_id, feishu_app_secret,
               feishu_app_token, main_table_id, deepseek_api_key, deepseek_model)
               VALUES (?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(user_id) DO UPDATE SET
               feishu_app_id=excluded.feishu_app_id,
               feishu_app_secret=excluded.feishu_app_secret,
               feishu_app_token=excluded.feishu_app_token,
               main_table_id=excluded.main_table_id,
               deepseek_api_key=excluded.deepseek_api_key,
               deepseek_model=excluded.deepseek_model""",
            (
                user_id,
                config.get("FEISHU_APP_ID", ""),
                config.get("FEISHU_APP_SECRET", ""),
                config.get("FEISHU_APP_TOKEN", ""),
                config.get("MAIN_TABLE_ID", ""),
                config.get("DEEPSEEK_API_KEY", ""),
                config.get("DEEPSEEK_MODEL", "deepseek-v4-flash"),
            ),
        )
        db.commit()


# ── 本地日程（per-user）─────────────────────────────

def get_local_events(user_id: int) -> list[dict]:
    db = get_db()
    rows = db.execute(
        "SELECT id, date, label FROM local_events WHERE user_id = ? ORDER BY date",
        (user_id,),
    ).fetchall()
    return [{"id": r["id"], "date": r["date"], "label": r["label"]} for r in rows]


def add_local_event(user_id: int, event_id: str, date: str, label: str) -> None:
    with _write_lock:
        db = get_db()
        db.execute(
            "INSERT INTO local_events (id, user_id, date, label) VALUES (?, ?, ?, ?)",
            (event_id, user_id, date, label),
        )
        db.commit()


def delete_local_event(user_id: int, event_id: str) -> bool:
    with _write_lock:
        db = get_db()
        cur = db.execute(
            "DELETE FROM local_events WHERE id = ? AND user_id = ?",
            (event_id, user_id),
        )
        db.commit()
        return cur.rowcount > 0
