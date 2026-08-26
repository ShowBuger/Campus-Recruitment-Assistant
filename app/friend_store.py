"""Friend requests and accepted friendship persistence."""
from __future__ import annotations

from app import database


def are_friends(user_id: int, friend_id: int) -> bool:
    row = database.get_db().execute(
        "SELECT 1 FROM friendships WHERE user_id = ? AND friend_id = ?",
        (user_id, friend_id),
    ).fetchone()
    return row is not None


def create_request(sender_id: int, username: str) -> dict:
    username = username.strip()
    db = database.get_db()
    receiver = db.execute(
        "SELECT id, username, nickname FROM users WHERE username = ? COLLATE NOCASE",
        (username,),
    ).fetchone()
    if not receiver:
        raise LookupError("未找到该用户名")
    receiver = dict(receiver)
    if receiver["id"] == sender_id:
        raise ValueError("不能添加自己为好友")
    if are_friends(sender_id, receiver["id"]):
        raise ValueError("你们已经是好友")
    reverse = db.execute(
        """SELECT id FROM friend_requests
           WHERE sender_id = ? AND receiver_id = ? AND status = 'pending'""",
        (receiver["id"], sender_id),
    ).fetchone()
    if reverse:
        raise ValueError("对方已向你发送好友申请，请前往通知中心处理")
    existing = db.execute(
        """SELECT id FROM friend_requests
           WHERE sender_id = ? AND receiver_id = ? AND status = 'pending'""",
        (sender_id, receiver["id"]),
    ).fetchone()
    if existing:
        raise ValueError("好友申请已发送，请等待对方处理")
    with database._write_lock:
        cur = db.execute(
            "INSERT INTO friend_requests (sender_id, receiver_id) VALUES (?, ?)",
            (sender_id, receiver["id"]),
        )
        db.commit()
    return {"id": cur.lastrowid, "receiver": receiver, "status": "pending"}


def list_received_requests(user_id: int, limit: int = 20) -> list[dict]:
    rows = database.get_db().execute(
        """SELECT fr.id, fr.status, fr.created_at, fr.responded_at,
                  u.id AS sender_id, u.username AS sender_username,
                  COALESCE(NULLIF(u.nickname, ''), u.username) AS sender_name,
                  COALESCE(NULLIF(u.avatar_key, ''), 'indigo') AS avatar_key,
                  CASE WHEN u.avatar_key = 'custom' AND u.avatar_file <> ''
                       THEN '/api/auth/users/' || u.id || '/avatar' ELSE '' END AS avatar_url
           FROM friend_requests fr JOIN users u ON u.id = fr.sender_id
           WHERE fr.receiver_id = ? ORDER BY fr.id DESC LIMIT ?""",
        (user_id, limit),
    ).fetchall()
    return [dict(row) for row in rows]


def count_pending_requests(user_id: int) -> int:
    row = database.get_db().execute(
        "SELECT COUNT(*) AS total FROM friend_requests WHERE receiver_id = ? AND status = 'pending'",
        (user_id,),
    ).fetchone()
    return int(row["total"])


def respond_to_request(user_id: int, request_id: int, accept: bool) -> dict:
    with database._write_lock:
        db = database.get_db()
        request = db.execute(
            """SELECT fr.*, u.username AS sender_username
               FROM friend_requests fr JOIN users u ON u.id = fr.sender_id
               WHERE fr.id = ? AND fr.receiver_id = ?""",
            (request_id, user_id),
        ).fetchone()
        if not request:
            raise LookupError("好友申请不存在")
        request = dict(request)
        if request["status"] != "pending":
            raise ValueError("该好友申请已处理")
        status = "accepted" if accept else "rejected"
        db.execute(
            "UPDATE friend_requests SET status = ?, responded_at = datetime('now') WHERE id = ?",
            (status, request_id),
        )
        if accept:
            db.executemany(
                "INSERT OR IGNORE INTO friendships (user_id, friend_id) VALUES (?, ?)",
                [(user_id, request["sender_id"]), (request["sender_id"], user_id)],
            )
        db.commit()
    return {"id": request_id, "status": status, "sender_username": request["sender_username"]}
