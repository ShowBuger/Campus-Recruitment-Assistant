"""Administrator tools and root-only account management."""
import shutil
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, field_validator

from app import auth as auth_module, database

router = APIRouter(prefix="/api", tags=["admin"])
PROJECT_DIR = Path(__file__).resolve().parents[2]
USER_DATA_DIR = PROJECT_DIR / "data" / "users"


def require_root(user: dict = Depends(auth_module.get_current_user)) -> dict:
    if not user.get("is_root"):
        raise HTTPException(status_code=403, detail="仅 root 用户可以执行此操作")
    return user


def require_admin(user: dict = Depends(auth_module.get_current_user)) -> dict:
    if not (user.get("is_root") or user.get("is_admin")):
        raise HTTPException(status_code=403, detail="仅管理员可以执行此操作")
    return user


class PasswordUpdate(BaseModel):
    password: str

    @field_validator("password")
    @classmethod
    def validate_password(cls, value: str) -> str:
        if not 4 <= len(value) <= 100:
            raise ValueError("密码需为 4-100 个字符")
        return value


class AdminUpdate(BaseModel):
    is_admin: bool


class NotificationCreate(BaseModel):
    title: str
    content: str
    request_id: str = ""

    @field_validator("title")
    @classmethod
    def validate_title(cls, value: str) -> str:
        value = value.strip()
        if not value or len(value) > 100:
            raise ValueError("通知标题需为 1-100 个字符")
        return value

    @field_validator("content")
    @classmethod
    def validate_content(cls, value: str) -> str:
        value = value.strip()
        if not value or len(value) > 5000:
            raise ValueError("通知内容需为 1-5000 个字符")
        return value

    @field_validator("request_id")
    @classmethod
    def validate_request_id(cls, value: str) -> str:
        value = value.strip()
        if len(value) > 100:
            raise ValueError("请求 ID 不能超过 100 个字符")
        return value


class NotificationRead(BaseModel):
    ids: list[int]


@router.get("/admin/users")
def get_users(_: dict = Depends(require_admin)):
    users = database.list_users()
    for user in users:
        user["is_admin"] = bool(user["is_admin"])
        user["is_online"] = bool(user["is_online"])
        user["is_root"] = user["username"] == "root"
    return {"success": True, "users": users}


@router.get("/admin/invite-codes")
def get_invite_codes(_: dict = Depends(require_admin)):
    return {"success": True, "invite_codes": database.list_invite_codes()}


@router.post("/admin/invite-codes")
def generate_invite_code(user: dict = Depends(require_admin)):
    invite = database.create_invite_code(user["user_id"])
    return {"success": True, "message": "邀请码已生成", "invite_code": invite}


@router.post("/admin/invite-codes/{code}/revoke")
def revoke_invite_code(code: str, _: dict = Depends(require_admin)):
    if not database.revoke_invite_code(code):
        raise HTTPException(status_code=409, detail="邀请码不存在、已使用或已作废")
    return {"success": True, "message": "邀请码已作废"}


@router.patch("/admin/users/{user_id}/password")
@router.post("/admin/users/{user_id}/password")
@router.post("/admin/users/{user_id}/password/update")
def change_password(
    user_id: int,
    body: PasswordUpdate,
    _: dict = Depends(require_root),
):
    if not database.update_user_password(user_id, auth_module.hash_password(body.password)):
        raise HTTPException(status_code=404, detail="用户不存在")
    return {"success": True, "message": "密码已更新"}


@router.patch("/admin/users/{user_id}/admin")
@router.post("/admin/users/{user_id}/admin")
@router.post("/admin/users/{user_id}/admin/update")
def change_admin(
    user_id: int,
    body: AdminUpdate,
    _: dict = Depends(require_root),
):
    target = database.get_user_by_id(user_id)
    if not target:
        raise HTTPException(status_code=404, detail="用户不存在")
    if target["username"] == "root":
        raise HTTPException(status_code=400, detail="root 的管理员权限不能撤销")
    database.set_user_admin(user_id, body.is_admin)
    return {"success": True, "message": "管理员权限已更新"}


def _remove_user(user_id: int) -> dict:
    target = database.get_user_by_id(user_id)
    if not target:
        raise HTTPException(status_code=404, detail="用户不存在")
    if target["username"] == "root":
        raise HTTPException(status_code=400, detail="root 账号不能删除")
    if not database.delete_user(user_id):
        raise HTTPException(status_code=409, detail="用户删除失败")

    user_dir = (USER_DATA_DIR / str(user_id)).resolve()
    data_root = USER_DATA_DIR.resolve()
    if user_dir.parent == data_root and user_dir.exists():
        shutil.rmtree(user_dir)
    return {"success": True, "message": "用户账号及本地数据已删除"}


@router.delete("/admin/users/{user_id}")
def remove_user(user_id: int, _: dict = Depends(require_root)):
    return _remove_user(user_id)


@router.post("/admin/users/{user_id}/delete")
def remove_user_compat(user_id: int, _: dict = Depends(require_root)):
    """兼容部分入口代理不转发 DELETE 方法的部署环境。"""
    return _remove_user(user_id)


@router.post("/admin/notifications")
def publish_notification(
    body: NotificationCreate,
    user: dict = Depends(require_admin),
):
    notification = database.create_notification(
        body.title,
        body.content,
        user["user_id"],
        body.request_id,
    )
    return {"success": True, "message": "通知已发布", "notification": notification}


@router.get("/notifications")
def get_notifications(user: dict = Depends(auth_module.get_current_user)):
    notifications = database.list_notifications(user["user_id"])
    return {
        "success": True,
        "notifications": notifications,
        "unread_count": database.count_unread_notifications(user["user_id"]),
    }


@router.post("/notifications/read")
def read_notifications(
    body: NotificationRead,
    user: dict = Depends(auth_module.get_current_user),
):
    database.mark_notifications_read(user["user_id"], list(dict.fromkeys(body.ids)))
    return {"success": True}
