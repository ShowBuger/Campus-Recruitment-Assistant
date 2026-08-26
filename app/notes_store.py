"""Authenticated, user-scoped Markdown note persistence."""
from __future__ import annotations

import uuid

from app import database, local_records


def _serialize(row) -> dict:
    return {
        "id": row["id"],
        "parent_id": row["parent_id"],
        "record_id": row["record_id"],
        "title": row["title"] or "未命名笔记",
        "content": row["content"] or "",
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
        "record": (
            {
                "company": row["record_company"] or "",
                "job": row["record_job"] or "",
            }
            if row["record_id"] else None
        ),
    }


def _select_sql(where: str) -> str:
    return f"""SELECT n.*,
                      r.company AS record_company,
                      r.job AS record_job
               FROM notes n
               LEFT JOIN job_records r
                 ON r.id = n.record_id AND r.user_id = n.user_id
               WHERE {where}"""


def list_notes(user_id: int) -> list[dict]:
    db = database.get_db()
    rows = db.execute(
        _select_sql("n.user_id = ?") + " ORDER BY n.created_at, n.id",
        (user_id,),
    ).fetchall()
    return [_serialize(row) for row in rows]


def get_note(user_id: int, note_id: str) -> dict | None:
    db = database.get_db()
    row = db.execute(
        _select_sql("n.user_id = ? AND n.id = ?"),
        (user_id, note_id),
    ).fetchone()
    return _serialize(row) if row else None


def _validate_links(
    user_id: int, parent_id: str | None, record_id: str | None,
) -> None:
    if parent_id and not get_note(user_id, parent_id):
        raise ValueError("父笔记不存在")
    if record_id and not local_records.get_record(user_id, record_id):
        raise ValueError("关联的投递记录不存在")


def create_note(
    user_id: int,
    title: str,
    parent_id: str | None = None,
    record_id: str | None = None,
) -> dict:
    _validate_links(user_id, parent_id, record_id)
    note_id = "note" + uuid.uuid4().hex
    clean_title = title.strip() or "未命名笔记"
    with database._write_lock:
        db = database.get_db()
        db.execute(
            """INSERT INTO notes (id, user_id, parent_id, record_id, title)
               VALUES (?, ?, ?, ?, ?)""",
            (note_id, user_id, parent_id, record_id, clean_title),
        )
        db.commit()
    return get_note(user_id, note_id)


def update_note(
    user_id: int,
    note_id: str,
    title: str,
    content: str,
    record_id: str | None,
) -> dict | None:
    if record_id and not local_records.get_record(user_id, record_id):
        raise ValueError("关联的投递记录不存在")
    clean_title = title.strip() or "未命名笔记"
    with database._write_lock:
        db = database.get_db()
        cursor = db.execute(
            """UPDATE notes
               SET title = ?, content = ?, record_id = ?, updated_at = datetime('now')
               WHERE id = ? AND user_id = ?""",
            (clean_title, content, record_id, note_id, user_id),
        )
        db.commit()
    return get_note(user_id, note_id) if cursor.rowcount else None


def delete_note(user_id: int, note_id: str) -> bool:
    with database._write_lock:
        db = database.get_db()
        cursor = db.execute(
            "DELETE FROM notes WHERE id = ? AND user_id = ?",
            (note_id, user_id),
        )
        db.commit()
    return bool(cursor.rowcount)
