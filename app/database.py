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

        CREATE TABLE IF NOT EXISTS notifications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            content TEXT NOT NULL,
            created_by INTEGER,
            created_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (created_by) REFERENCES users(id) ON DELETE SET NULL
        );

        CREATE TABLE IF NOT EXISTS notification_reads (
            user_id INTEGER NOT NULL,
            notification_id INTEGER NOT NULL,
            read_at TEXT DEFAULT (datetime('now')),
            PRIMARY KEY (user_id, notification_id),
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY (notification_id) REFERENCES notifications(id) ON DELETE CASCADE
        );
    """)
    columns = {row["name"] for row in conn.execute("PRAGMA table_info(users)")}
    if "is_admin" not in columns:
        conn.execute("ALTER TABLE users ADD COLUMN is_admin INTEGER NOT NULL DEFAULT 0")
    conn.execute("UPDATE users SET is_admin = 1 WHERE username = 'root'")
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


def list_users() -> list[dict]:
    db = get_db()
    rows = db.execute(
        "SELECT id, username, is_admin, created_at FROM users ORDER BY id"
    ).fetchall()
    return [dict(row) for row in rows]


def update_user_password(user_id: int, password_hash: str) -> bool:
    with _write_lock:
        db = get_db()
        cur = db.execute(
            "UPDATE users SET password_hash = ? WHERE id = ?",
            (password_hash, user_id),
        )
        db.commit()
        return cur.rowcount > 0


def set_user_admin(user_id: int, is_admin: bool) -> bool:
    with _write_lock:
        db = get_db()
        cur = db.execute(
            "UPDATE users SET is_admin = ? WHERE id = ? AND username <> 'root'",
            (1 if is_admin else 0, user_id),
        )
        db.commit()
        return cur.rowcount > 0


def delete_user(user_id: int) -> bool:
    with _write_lock:
        db = get_db()
        cur = db.execute(
            "DELETE FROM users WHERE id = ? AND username <> 'root'", (user_id,)
        )
        db.commit()
        return cur.rowcount > 0


# ── 全局通知 ─────────────────────────────────────────

def create_notification(title: str, content: str, created_by: int) -> dict:
    with _write_lock:
        db = get_db()
        cur = db.execute(
            "INSERT INTO notifications (title, content, created_by) VALUES (?, ?, ?)",
            (title, content, created_by),
        )
        db.commit()
        row = db.execute(
            "SELECT id, title, content, created_at FROM notifications WHERE id = ?",
            (cur.lastrowid,),
        ).fetchone()
        return dict(row)


def list_notifications(user_id: int, limit: int = 20) -> list[dict]:
    db = get_db()
    rows = db.execute(
        """SELECT n.id, n.title, n.content, n.created_at,
                  CASE WHEN r.user_id IS NULL THEN 0 ELSE 1 END AS is_read
           FROM notifications n
           LEFT JOIN notification_reads r
             ON r.notification_id = n.id AND r.user_id = ?
           ORDER BY n.id DESC LIMIT ?""",
        (user_id, limit),
    ).fetchall()
    return [dict(row) for row in rows]


def count_unread_notifications(user_id: int) -> int:
    db = get_db()
    row = db.execute(
        """SELECT COUNT(*) AS total FROM notifications n
           LEFT JOIN notification_reads r
             ON r.notification_id = n.id AND r.user_id = ?
           WHERE r.user_id IS NULL""",
        (user_id,),
    ).fetchone()
    return int(row["total"])


def mark_notifications_read(user_id: int, notification_ids: list[int]) -> None:
    if not notification_ids:
        return
    with _write_lock:
        db = get_db()
        db.executemany(
            "INSERT OR IGNORE INTO notification_reads (user_id, notification_id) VALUES (?, ?)",
            [(user_id, notification_id) for notification_id in notification_ids],
        )
        db.commit()


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
