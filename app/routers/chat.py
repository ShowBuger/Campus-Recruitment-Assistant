"""Authenticated one-to-one chat APIs."""
from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, field_validator

from app import auth as auth_module, chat_store, database, local_records, state

router = APIRouter(prefix="/api/chat", tags=["chat"])
DATA_USERS = Path(__file__).resolve().parents[2] / "data" / "users"
MAX_IMAGE_SIZE = 5 * 1024 * 1024


class TextMessage(BaseModel):
    receiver_id: int
    text: str

    @field_validator("text")
    @classmethod
    def validate_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("消息不能为空")
        if len(value) > 3000:
            raise ValueError("消息不能超过 3000 个字符")
        return value


class JobMessage(BaseModel):
    receiver_id: int
    source: Literal["personal", "shared"]
    record_id: str


def _ensure_peer(user_id: int, peer_id: int) -> None:
    if user_id == peer_id:
        raise HTTPException(status_code=422, detail="不能给自己发送消息")
    if not database.get_user_by_id(peer_id):
        raise HTTPException(status_code=404, detail="用户不存在")


def _image_type(data: bytes) -> tuple[str, str] | None:
    if data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg", ".jpg"
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png", ".png"
    if data.startswith((b"GIF87a", b"GIF89a")):
        return "image/gif", ".gif"
    if len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp", ".webp"
    return None


def _snapshot_from_fields(fields: dict) -> dict:
    company_type = fields.get("公司/行业类型") or ""
    if isinstance(company_type, list):
        company_type = company_type[0] if company_type else ""
    directions = fields.get("嵌入式方向") or []
    if not isinstance(directions, list):
        directions = [directions] if directions else []
    url = fields.get("投递链接") or ""
    if isinstance(url, dict):
        url = url.get("link") or url.get("text") or ""
    return {
        "company": str(fields.get("公司名称") or "").strip(),
        "company_type": str(company_type or "").strip(),
        "directions": [str(item).strip() for item in directions if str(item).strip()],
        "job": str(fields.get("秋招岗位") or "").strip(),
        "city": str(fields.get("城市") or "").strip(),
        "batch": str(fields.get("批次") or "秋招").strip() or "秋招",
        "url": str(url or "").strip(),
        "deadline": fields.get("投递截止时间") or None,
    }


@router.get("/users")
def chat_users(user: dict = Depends(auth_module.get_current_user)):
    users = chat_store.list_chat_users(user["user_id"])
    return {"users": users, "unread_count": sum(item["unread_count"] for item in users)}


@router.get("/messages/{peer_id}")
def messages(peer_id: int, user: dict = Depends(auth_module.get_current_user)):
    _ensure_peer(user["user_id"], peer_id)
    return {"messages": chat_store.list_messages(user["user_id"], peer_id)}


@router.post("/messages/text")
def send_text(body: TextMessage, user: dict = Depends(auth_module.get_current_user)):
    _ensure_peer(user["user_id"], body.receiver_id)
    return {"success": True, "message": chat_store.create_message(
        user["user_id"], body.receiver_id, "text", content=body.text
    )}


@router.post("/messages/image")
async def send_image(
    receiver_id: int = Form(...),
    file: UploadFile = File(...),
    user: dict = Depends(auth_module.get_current_user),
):
    _ensure_peer(user["user_id"], receiver_id)
    data = await file.read(MAX_IMAGE_SIZE + 1)
    if len(data) > MAX_IMAGE_SIZE:
        raise HTTPException(status_code=413, detail="图片不能超过 5MB")
    detected = _image_type(data)
    if not detected:
        raise HTTPException(status_code=415, detail="仅支持 JPEG、PNG、GIF 或 WebP 图片")
    mime, extension = detected
    relative = Path(str(user["user_id"])) / "chat" / f"{uuid.uuid4().hex}{extension}"
    target = DATA_USERS / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(data)
    try:
        message = chat_store.create_message(
            user["user_id"], receiver_id, "image",
            content=(file.filename or "图片")[:255],
            image_path=relative.as_posix(), image_mime=mime,
        )
    except Exception:
        target.unlink(missing_ok=True)
        raise
    return {"success": True, "message": message}


@router.get("/messages/{message_id}/image")
def message_image(message_id: int, user: dict = Depends(auth_module.get_current_user)):
    message = chat_store.get_message_for_user(message_id, user["user_id"])
    if not message or message["kind"] != "image":
        raise HTTPException(status_code=404, detail="图片不存在")
    root = DATA_USERS.resolve()
    path = (DATA_USERS / message["image_path"]).resolve()
    if root not in path.parents or not path.is_file():
        raise HTTPException(status_code=404, detail="图片不存在")
    return FileResponse(
        path, media_type=message["image_mime"] or "application/octet-stream",
        headers={"Cache-Control": "private, max-age=3600"},
    )


@router.post("/messages/job")
def send_job(body: JobMessage, user: dict = Depends(auth_module.get_current_user)):
    _ensure_peer(user["user_id"], body.receiver_id)
    if body.source == "personal":
        record = local_records.get_record(user["user_id"], body.record_id)
        if not record:
            raise HTTPException(status_code=404, detail="个人总表中未找到该岗位")
        payload = _snapshot_from_fields(record["fields"])
    else:
        db = database.get_db()
        row = db.execute("SELECT * FROM shared_job_records WHERE id = ?", (body.record_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="共享总表中未找到该岗位")
        row = dict(row)
        try:
            directions = json.loads(row.get("directions") or "[]")
        except json.JSONDecodeError:
            directions = []
        if not isinstance(directions, list):
            directions = [directions] if directions else []
        payload = {
            "company": row.get("company") or "", "company_type": row.get("company_type") or "",
            "directions": directions, "job": row.get("job") or "", "city": row.get("city") or "",
            "batch": row.get("batch") or "秋招", "url": row.get("url") or "",
            "deadline": row.get("deadline"),
        }
    if not payload["company"]:
        raise HTTPException(status_code=422, detail="岗位信息缺少公司名称")
    return {"success": True, "message": chat_store.create_message(
        user["user_id"], body.receiver_id, "job", content=payload["company"], payload=payload
    )}


@router.post("/messages/{message_id}/copy-job")
def copy_job(message_id: int, user: dict = Depends(auth_module.get_current_user)):
    try:
        record_id, created = chat_store.copy_job_message(user["user_id"], message_id)
        dashboard = local_records.get_dashboard_data(user["user_id"])
        state.set_cache(user["user_id"], dashboard)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {
        "success": True, "created": created, "record_id": record_id,
        "message": "已添加到个人总表" if created else "该岗位已添加过",
        "dashboard": dashboard,
    }
