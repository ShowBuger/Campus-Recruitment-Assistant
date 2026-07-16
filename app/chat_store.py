"""SQLite persistence helpers for authenticated one-to-one chat."""
from __future__ import annotations

import json
import uuid

from app import database


def list_chat_users(current_user_id: int) -> list[dict]:
    db = database.get_db()
    rows = db.execute(
        """SELECT u.id, u.username, u.last_seen_at,
                  CASE WHEN u.last_seen_at >= datetime('now', '-2 minutes')
                       THEN 1 ELSE 0 END AS is_online,
                  COALESCE((
                      SELECT COUNT(*) FROM chat_messages unread
                      WHERE unread.receiver_id = ? AND unread.sender_id = u.id
                        AND unread.id > COALESCE((
                            SELECT last_read_id FROM chat_reads
                            WHERE user_id = ? AND peer_id = u.id
                        ), 0)
                  ), 0) AS unread_count,
                  (SELECT kind FROM chat_messages latest
                   WHERE (latest.sender_id = ? AND latest.receiver_id = u.id)
                      OR (latest.sender_id = u.id AND latest.receiver_id = ?)
                   ORDER BY latest.id DESC LIMIT 1) AS last_kind,
                  (SELECT content FROM chat_messages latest
                   WHERE (latest.sender_id = ? AND latest.receiver_id = u.id)
                      OR (latest.sender_id = u.id AND latest.receiver_id = ?)
                   ORDER BY latest.id DESC LIMIT 1) AS last_content,
                  (SELECT created_at FROM chat_messages latest
                   WHERE (latest.sender_id = ? AND latest.receiver_id = u.id)
                      OR (latest.sender_id = u.id AND latest.receiver_id = ?)
                   ORDER BY latest.id DESC LIMIT 1) AS last_message_at
           FROM users u WHERE u.id <> ?
           ORDER BY (last_message_at IS NULL), last_message_at DESC, u.username""",
        (
            current_user_id, current_user_id,
            current_user_id, current_user_id,
            current_user_id, current_user_id,
            current_user_id, current_user_id,
            current_user_id,
        ),
    ).fetchall()
    return [
        {
            **dict(row),
            "is_online": bool(row["is_online"]),
            "unread_count": int(row["unread_count"] or 0),
        }
        for row in rows
    ]


def create_message(
    sender_id: int,
    receiver_id: int,
    kind: str,
    content: str = "",
    payload: dict | None = None,
    image_path: str = "",
    image_mime: str = "",
) -> dict:
    with database._write_lock:
        db = database.get_db()
        cur = db.execute(
            """INSERT INTO chat_messages
               (sender_id, receiver_id, kind, content, payload, image_path, image_mime)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                sender_id, receiver_id, kind, content,
                json.dumps(payload or {}, ensure_ascii=False), image_path, image_mime,
            ),
        )
        db.commit()
        row = db.execute("SELECT * FROM chat_messages WHERE id = ?", (cur.lastrowid,)).fetchone()
    return serialize_message(dict(row), sender_id)


def serialize_message(row: dict, current_user_id: int) -> dict:
    try:
        payload = json.loads(row.get("payload") or "{}")
    except (TypeError, json.JSONDecodeError):
        payload = {}
    return {
        "id": row["id"],
        "sender_id": row["sender_id"],
        "receiver_id": row["receiver_id"],
        "kind": row["kind"],
        "content": row.get("content") or "",
        "payload": payload if isinstance(payload, dict) else {},
        "created_at": row.get("created_at") or "",
        "is_mine": row["sender_id"] == current_user_id,
        "copied": bool(row.get("copied", 0)),
    }


def list_messages(current_user_id: int, peer_id: int, limit: int = 100) -> list[dict]:
    db = database.get_db()
    rows = db.execute(
        """SELECT m.*, EXISTS(
                      SELECT 1 FROM chat_job_copies c
                      WHERE c.message_id = m.id AND c.user_id = ?
                  ) AS copied
           FROM chat_messages m
           WHERE (m.sender_id = ? AND m.receiver_id = ?)
              OR (m.sender_id = ? AND m.receiver_id = ?)
           ORDER BY m.id DESC LIMIT ?""",
        (current_user_id, current_user_id, peer_id, peer_id, current_user_id, limit),
    ).fetchall()
    messages = [serialize_message(dict(row), current_user_id) for row in reversed(rows)]
    received_ids = [m["id"] for m in messages if m["sender_id"] == peer_id]
    if received_ids:
        mark_read(current_user_id, peer_id, max(received_ids))
    return messages


def mark_read(user_id: int, peer_id: int, last_read_id: int) -> None:
    with database._write_lock:
        db = database.get_db()
        db.execute(
            """INSERT INTO chat_reads (user_id, peer_id, last_read_id)
               VALUES (?, ?, ?)
               ON CONFLICT(user_id, peer_id) DO UPDATE SET
                   last_read_id = MAX(chat_reads.last_read_id, excluded.last_read_id)""",
            (user_id, peer_id, last_read_id),
        )
        db.commit()


def get_message_for_user(message_id: int, user_id: int) -> dict | None:
    db = database.get_db()
    row = db.execute(
        """SELECT * FROM chat_messages
           WHERE id = ? AND (sender_id = ? OR receiver_id = ?)""",
        (message_id, user_id, user_id),
    ).fetchone()
    return dict(row) if row else None


def copy_job_message(user_id: int, message_id: int) -> tuple[str, bool]:
    with database._write_lock:
        db = database.get_db()
        message = db.execute(
            """SELECT * FROM chat_messages
               WHERE id = ? AND receiver_id = ? AND kind = 'job'""",
            (message_id, user_id),
        ).fetchone()
        if not message:
            raise LookupError("未找到可添加的岗位消息")
        existing = db.execute(
            """SELECT record_id FROM chat_job_copies
               WHERE message_id = ? AND user_id = ?""",
            (message_id, user_id),
        ).fetchone()
        if existing:
            return existing["record_id"], False
        try:
            payload = json.loads(message["payload"] or "{}")
        except (TypeError, json.JSONDecodeError) as exc:
            raise ValueError("岗位信息已损坏") from exc
        company = str(payload.get("company") or "").strip()
        if not company:
            raise ValueError("岗位信息缺少公司名称")
        directions = payload.get("directions") or []
        if not isinstance(directions, list):
            directions = [directions] if directions else []
        record_id = "rec" + uuid.uuid4().hex
        try:
            db.execute(
                """INSERT INTO job_records
               (id, user_id, company, company_type, directions, progress, job,
                city, batch, url, deadline)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    record_id, user_id, company,
                    str(payload.get("company_type") or "").strip(),
                    json.dumps(directions, ensure_ascii=False),
                    json.dumps(["未投递"], ensure_ascii=False),
                    str(payload.get("job") or "").strip(),
                    str(payload.get("city") or "").strip(),
                    str(payload.get("batch") or "秋招").strip() or "秋招",
                    str(payload.get("url") or "").strip(), payload.get("deadline"),
                ),
            )
            db.execute(
                """INSERT INTO chat_job_copies (message_id, user_id, record_id)
               VALUES (?, ?, ?)""",
                (message_id, user_id, record_id),
            )
            db.commit()
        except Exception:
            db.rollback()
            raise
        return record_id, True
