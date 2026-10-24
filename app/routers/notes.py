"""Markdown notes API with nested notes and application links."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app import auth as auth_module, local_records, notes_store

router = APIRouter(prefix="/api/notes", tags=["notes"])


class NoteCreate(BaseModel):
    title: str = Field(default="未命名笔记", max_length=200)
    parent_id: str | None = Field(default=None, max_length=100)
    record_id: str | None = Field(default=None, max_length=100)


class NoteUpdate(BaseModel):
    title: str = Field(max_length=200)
    content: str = Field(default="", max_length=1_000_000)
    record_id: str | None = Field(default=None, max_length=100)


@router.get("")
def list_user_notes(user: dict = Depends(auth_module.get_current_user)):
    return {"notes": notes_store.list_notes(user["user_id"])}


@router.get("/records")
def list_note_records(user: dict = Depends(auth_module.get_current_user)):
    records = local_records.list_records(user["user_id"])
    return {
        "records": [
            {
                "record_id": record["record_id"],
                "company": record["fields"].get("公司名称") or "未命名公司",
                "job": record["fields"].get("秋招岗位") or "未命名岗位",
            }
            for record in records
        ]
    }


@router.post("")
def create_user_note(
    body: NoteCreate,
    user: dict = Depends(auth_module.get_current_user),
):
    try:
        note = notes_store.create_note(
            user["user_id"], body.title, body.parent_id, body.record_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"success": True, "note": note}


@router.put("/{note_id}")
@router.post("/{note_id}/update")
def update_user_note(
    note_id: str,
    body: NoteUpdate,
    user: dict = Depends(auth_module.get_current_user),
):
    try:
        note = notes_store.update_note(
            user["user_id"], note_id, body.title, body.content, body.record_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if not note:
        raise HTTPException(status_code=404, detail="笔记不存在")
    return {"success": True, "note": note}


@router.delete("/{note_id}")
@router.post("/{note_id}/delete")
def delete_user_note(
    note_id: str,
    user: dict = Depends(auth_module.get_current_user),
):
    if not notes_store.delete_note(user["user_id"], note_id):
        raise HTTPException(status_code=404, detail="笔记不存在")
    return {"success": True, "message": "笔记已删除"}
