"""SQLite 数据库：用户账号、独立配置、本地日程持久化。"""
import sqlite3
import os
import secrets
import threading
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / "data"
DB_PATH = DATA_DIR / "app.db"

# 写锁，防止并发写入冲突
_write_lock = threading.Lock()


def _ensure_dir() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)


_tables_initialized = False


_thread_local = threading.local()

def get_db() -> sqlite3.Connection:
    """获取数据库连接（线程级复用），自动初始化表结构。"""
    global _tables_initialized
    _ensure_dir()
    cached = getattr(_thread_local, "conn", None)
    if cached is not None:
        return cached
    conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA cache_size=-8000")  # 8MB cache
    if not _tables_initialized:
        with _write_lock:
            if not _tables_initialized:
                _init_tables(conn)
                _tables_initialized = True
    _thread_local.conn = conn
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
            ai_provider TEXT NOT NULL DEFAULT 'deepseek',
            deepseek_api_key TEXT DEFAULT '',
            deepseek_model TEXT DEFAULT 'deepseek-v4-flash',
            deepseek_base_url TEXT DEFAULT 'https://api.deepseek.com',
            openai_api_key TEXT DEFAULT '',
            openai_model TEXT DEFAULT 'gpt-5.4-mini',
            openai_base_url TEXT DEFAULT 'https://api.openai.com/v1',
            openai_api_mode TEXT DEFAULT 'responses',
            anthropic_api_key TEXT DEFAULT '',
            anthropic_model TEXT DEFAULT 'claude-sonnet-5',
            anthropic_base_url TEXT DEFAULT 'https://api.anthropic.com/v1',
            apidock_api_key TEXT DEFAULT '',
            apidock_model TEXT DEFAULT 'gpt-4o',
            apidock_base_url TEXT DEFAULT 'https://apidock.ai/v1',
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS invite_codes (
            code TEXT PRIMARY KEY,
            created_by INTEGER,
            created_at TEXT DEFAULT (datetime('now')),
            used_by INTEGER,
            used_at TEXT,
            revoked INTEGER NOT NULL DEFAULT 0,
            FOREIGN KEY (created_by) REFERENCES users(id) ON DELETE SET NULL,
            FOREIGN KEY (used_by) REFERENCES users(id) ON DELETE SET NULL
        );

        CREATE TABLE IF NOT EXISTS chat_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sender_id INTEGER NOT NULL,
            receiver_id INTEGER NOT NULL,
            kind TEXT NOT NULL CHECK(kind IN ('text', 'image', 'job')),
            content TEXT NOT NULL DEFAULT '',
            payload TEXT NOT NULL DEFAULT '{}',
            image_path TEXT NOT NULL DEFAULT '',
            image_mime TEXT NOT NULL DEFAULT '',
            created_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (sender_id) REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY (receiver_id) REFERENCES users(id) ON DELETE CASCADE
        );

        CREATE INDEX IF NOT EXISTS idx_chat_messages_pair
            ON chat_messages(sender_id, receiver_id, id);
        CREATE INDEX IF NOT EXISTS idx_chat_messages_receiver
            ON chat_messages(receiver_id, id);

        CREATE TABLE IF NOT EXISTS chat_reads (
            user_id INTEGER NOT NULL,
            peer_id INTEGER NOT NULL,
            last_read_id INTEGER NOT NULL DEFAULT 0,
            PRIMARY KEY (user_id, peer_id),
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY (peer_id) REFERENCES users(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS chat_job_copies (
            message_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            record_id TEXT NOT NULL,
            copied_at TEXT DEFAULT (datetime('now')),
            PRIMARY KEY (message_id, user_id),
            FOREIGN KEY (message_id) REFERENCES chat_messages(id) ON DELETE CASCADE,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY (record_id) REFERENCES job_records(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS local_events (
            id TEXT PRIMARY KEY,
            user_id INTEGER NOT NULL,
            date TEXT NOT NULL,
            label TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS job_records (
            id TEXT PRIMARY KEY,
            user_id INTEGER NOT NULL,
            company TEXT NOT NULL DEFAULT '',
            company_type TEXT NOT NULL DEFAULT '',
            directions TEXT NOT NULL DEFAULT '[]',
            progress TEXT NOT NULL DEFAULT '[]',
            job TEXT NOT NULL DEFAULT '',
            city TEXT NOT NULL DEFAULT '',
            batch TEXT NOT NULL DEFAULT '',
            priority TEXT NOT NULL DEFAULT '',
            note TEXT NOT NULL DEFAULT '',
            job_jd TEXT NOT NULL DEFAULT '',
            url TEXT NOT NULL DEFAULT '',
            deadline INTEGER,
            apply_date INTEGER,
            exam_date INTEGER,
            interview1 INTEGER,
            interview2 INTEGER,
            interview3 INTEGER,
            warm INTEGER,
            result INTEGER,
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        );

        CREATE INDEX IF NOT EXISTS idx_job_records_user
            ON job_records(user_id, created_at);

        CREATE TABLE IF NOT EXISTS shared_job_records (
            id TEXT PRIMARY KEY,
            company TEXT NOT NULL,
            company_type TEXT NOT NULL,
            directions TEXT NOT NULL,
            job TEXT NOT NULL,
            city TEXT NOT NULL DEFAULT '',
            batch TEXT NOT NULL DEFAULT '秋招',
            url TEXT NOT NULL,
            deadline INTEGER,
            fingerprint TEXT NOT NULL UNIQUE,
            created_by INTEGER,
            created_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (created_by) REFERENCES users(id) ON DELETE SET NULL
        );

        CREATE INDEX IF NOT EXISTS idx_shared_job_records_created
            ON shared_job_records(created_at DESC);

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
    if "last_seen_at" not in columns:
        conn.execute("ALTER TABLE users ADD COLUMN last_seen_at TEXT")
    record_columns = {
        row["name"] for row in conn.execute("PRAGMA table_info(job_records)")
    }
    if "source_shared_id" not in record_columns:
        conn.execute("ALTER TABLE job_records ADD COLUMN source_shared_id TEXT")
    conn.execute(
        """CREATE UNIQUE INDEX IF NOT EXISTS idx_job_records_shared_source
           ON job_records(user_id, source_shared_id)
           WHERE source_shared_id IS NOT NULL"""
    )
    notification_columns = {
        row["name"] for row in conn.execute("PRAGMA table_info(notifications)")
    }
    if "request_id" not in notification_columns:
        conn.execute("ALTER TABLE notifications ADD COLUMN request_id TEXT")
    conn.execute(
        """CREATE UNIQUE INDEX IF NOT EXISTS idx_notifications_request_id
           ON notifications(request_id) WHERE request_id IS NOT NULL"""
    )
    config_columns = {
        row["name"] for row in conn.execute("PRAGMA table_info(user_configs)")
    }
    config_migrations = {
        "ai_provider": "TEXT NOT NULL DEFAULT 'deepseek'",
        "openai_api_key": "TEXT DEFAULT ''",
        "openai_model": "TEXT DEFAULT 'gpt-5.4-mini'",
        "openai_base_url": "TEXT DEFAULT 'https://api.openai.com/v1'",
        "openai_api_mode": "TEXT DEFAULT 'responses'",
        "anthropic_api_key": "TEXT DEFAULT ''",
        "anthropic_model": "TEXT DEFAULT 'claude-sonnet-5'",
        "anthropic_base_url": "TEXT DEFAULT 'https://api.anthropic.com/v1'",
        "apidock_api_key": "TEXT DEFAULT ''",
        "apidock_model": "TEXT DEFAULT 'gpt-4o'",
        "apidock_base_url": "TEXT DEFAULT 'https://apidock.ai/v1'",
        "deepseek_base_url": "TEXT DEFAULT 'https://api.deepseek.com'",
    }
    for column, declaration in config_migrations.items():
        if column not in config_columns:
            conn.execute(f"ALTER TABLE user_configs ADD COLUMN {column} {declaration}")
    conn.execute("UPDATE users SET is_admin = 1 WHERE username = 'root'")
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS system_config (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL DEFAULT ''
        );
    """)
    # Default sync schedule
    conn.execute(
        "INSERT OR IGNORE INTO system_config (key, value) VALUES ('sync_enabled', '0')"
    )
    conn.execute(
        "INSERT OR IGNORE INTO system_config (key, value) VALUES ('sync_time', '04:00')"
    )
    conn.commit()


# ── 系统配置 ─────────────────────────────────────────

def get_system_config(key: str) -> str | None:
    db = get_db()
    row = db.execute("SELECT value FROM system_config WHERE key = ?", (key,)).fetchone()
    return row["value"] if row else None


def set_system_config(key: str, value: str) -> None:
    with _write_lock:
        db = get_db()
        db.execute(
            "INSERT OR REPLACE INTO system_config (key, value) VALUES (?, ?)",
            (key, value),
        )
        db.commit()


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


def create_user_with_invite(
    username: str, password_hash: str, invite_code: str
) -> tuple[dict | None, str]:
    """Atomically consume a one-time invite and create its user."""
    code = invite_code.strip().upper()
    with _write_lock:
        db = get_db()
        try:
            db.execute("BEGIN IMMEDIATE")
            invite = db.execute(
                """SELECT code FROM invite_codes
                   WHERE code = ? AND revoked = 0 AND used_at IS NULL""",
                (code,),
            ).fetchone()
            if not invite:
                db.rollback()
                return None, "invalid_invite"
            cur = db.execute(
                "INSERT INTO users (username, password_hash) VALUES (?, ?)",
                (username, password_hash),
            )
            user_id = cur.lastrowid
            db.execute("INSERT INTO user_configs (user_id) VALUES (?)", (user_id,))
            consumed = db.execute(
                """UPDATE invite_codes
                   SET used_by = ?, used_at = datetime('now')
                   WHERE code = ? AND revoked = 0 AND used_at IS NULL""",
                (user_id, code),
            )
            if consumed.rowcount != 1:
                db.rollback()
                return None, "invalid_invite"
            db.commit()
            return {"id": user_id, "username": username}, "created"
        except sqlite3.IntegrityError:
            db.rollback()
            return None, "username_exists"
        except Exception:
            db.rollback()
            raise


def create_invite_code(created_by: int) -> dict:
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    with _write_lock:
        db = get_db()
        for _ in range(10):
            left = "".join(secrets.choice(alphabet) for _ in range(4))
            right = "".join(secrets.choice(alphabet) for _ in range(4))
            code = f"CRA-{left}-{right}"
            try:
                db.execute(
                    "INSERT INTO invite_codes (code, created_by) VALUES (?, ?)",
                    (code, created_by),
                )
                db.commit()
                row = db.execute(
                    "SELECT code, created_at FROM invite_codes WHERE code = ?",
                    (code,),
                ).fetchone()
                return dict(row)
            except sqlite3.IntegrityError:
                db.rollback()
        raise RuntimeError("邀请码生成冲突，请重试")


def list_invite_codes(limit: int = 100) -> list[dict]:
    db = get_db()
    rows = db.execute(
        """SELECT i.code, i.created_at, i.used_at, i.revoked,
                  creator.username AS created_by_name,
                  consumer.username AS used_by_name
           FROM invite_codes i
           LEFT JOIN users creator ON creator.id = i.created_by
           LEFT JOIN users consumer ON consumer.id = i.used_by
           ORDER BY i.created_at DESC, i.code DESC LIMIT ?""",
        (limit,),
    ).fetchall()
    return [dict(row) for row in rows]


def revoke_invite_code(code: str) -> bool:
    with _write_lock:
        db = get_db()
        cur = db.execute(
            """UPDATE invite_codes SET revoked = 1
               WHERE code = ? AND used_at IS NULL AND revoked = 0""",
            (code.strip().upper(),),
        )
        db.commit()
        return cur.rowcount > 0


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
        """SELECT id, username, is_admin, created_at, last_seen_at,
                  CASE WHEN last_seen_at >= datetime('now', '-2 minutes')
                       THEN 1 ELSE 0 END AS is_online
           FROM users ORDER BY id"""
    ).fetchall()
    return [dict(row) for row in rows]


def touch_user_last_seen(user_id: int) -> None:
    """Record authenticated activity, throttled to at most one write per 30 seconds."""
    with _write_lock:
        db = get_db()
        db.execute(
            """UPDATE users SET last_seen_at = datetime('now')
               WHERE id = ? AND (
                   last_seen_at IS NULL OR
                   last_seen_at < datetime('now', '-30 seconds')
               )""",
            (user_id,),
        )
        db.commit()


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

def create_notification(
    title: str,
    content: str,
    created_by: int,
    request_id: str = "",
) -> dict:
    request_id = request_id.strip() or None
    with _write_lock:
        db = get_db()
        db.execute(
            """INSERT OR IGNORE INTO notifications
               (title, content, created_by, request_id) VALUES (?, ?, ?, ?)""",
            (title, content, created_by, request_id),
        )
        db.commit()
        if request_id:
            row = db.execute(
                """SELECT id, title, content, created_at FROM notifications
                   WHERE request_id = ?""",
                (request_id,),
            ).fetchone()
        else:
            row = db.execute(
                """SELECT id, title, content, created_at FROM notifications
                   WHERE id = last_insert_rowid()"""
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


# ── 用户配置 ─────────────────────────────────────────

def get_user_config(user_id: int) -> dict:
    db = get_db()
    row = db.execute(
        "SELECT * FROM user_configs WHERE user_id = ?", (user_id,)
    ).fetchone()
    if not row:
        db.execute("INSERT INTO user_configs (user_id) VALUES (?)", (user_id,))
        db.commit()
        return {
            "ai_provider": "deepseek",
            "deepseek_api_key": "",
            "deepseek_model": "deepseek-v4-flash",
            "deepseek_base_url": "https://api.deepseek.com",
            "openai_api_key": "",
            "openai_model": "gpt-5.4-mini",
            "openai_base_url": "https://api.openai.com/v1",
            "openai_api_mode": "responses",
            "anthropic_api_key": "",
            "anthropic_model": "claude-sonnet-5",
            "anthropic_base_url": "https://api.anthropic.com/v1",
            "apidock_api_key": "",
            "apidock_model": "gpt-4o",
            "apidock_base_url": "https://apidock.ai/v1",
            "configured": False,
        }
    d = dict(row)
    d.pop("user_id", None)
    provider = d.get("ai_provider") or "deepseek"
    key_field = {
        "deepseek": "deepseek_api_key",
        "openai": "openai_api_key",
        "anthropic": "anthropic_api_key",
    }.get(provider, "deepseek_api_key")
    d["configured"] = bool(d.get(key_field))
    return d


def save_ai_config(user_id: int, values: dict) -> None:
    with _write_lock:
        db = get_db()
        db.execute(
            """INSERT INTO user_configs
               (user_id, ai_provider, deepseek_api_key, deepseek_model,
                deepseek_base_url, openai_api_key, openai_model, openai_base_url,
                openai_api_mode, anthropic_api_key, anthropic_model, anthropic_base_url,
                apidock_api_key, apidock_model, apidock_base_url)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(user_id) DO UPDATE SET
               ai_provider=excluded.ai_provider,
               deepseek_api_key=excluded.deepseek_api_key,
               deepseek_model=excluded.deepseek_model,
               deepseek_base_url=excluded.deepseek_base_url,
               openai_api_key=excluded.openai_api_key,
               openai_model=excluded.openai_model,
               openai_base_url=excluded.openai_base_url,
               openai_api_mode=excluded.openai_api_mode,
               anthropic_api_key=excluded.anthropic_api_key,
               anthropic_model=excluded.anthropic_model,
               anthropic_base_url=excluded.anthropic_base_url,
               apidock_api_key=excluded.apidock_api_key,
               apidock_model=excluded.apidock_model,
               apidock_base_url=excluded.apidock_base_url""",
            (
                user_id, values["ai_provider"],
                values["deepseek_api_key"], values["deepseek_model"], values["deepseek_base_url"],
                values["openai_api_key"], values["openai_model"], values["openai_base_url"],
                values["openai_api_mode"], values["anthropic_api_key"],
                values["anthropic_model"], values["anthropic_base_url"],
                values["apidock_api_key"], values["apidock_model"], values["apidock_base_url"],
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
