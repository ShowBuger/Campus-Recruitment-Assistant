"""认证接口：注册、登录、退出、获取当前用户信息。"""
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, field_validator

from app import auth as auth_module, bus, database

router = APIRouter(prefix="/api/auth", tags=["auth"])

USERNAME_PATTERN = r"^[a-zA-Z0-9_一-鿿]{2,20}$"
AVATAR_KEYS = {"indigo", "sunset", "forest", "ocean", "cherry", "mono", "cosmos", "spark", "custom"}
AVATAR_DIR = Path(__file__).resolve().parents[2] / "data" / "users"
MAX_AVATAR_SIZE = 2 * 1024 * 1024


class RegisterBody(BaseModel):
    username: str
    password: str
    invite_code: str

    @field_validator("username")
    @classmethod
    def check_username(cls, v: str) -> str:
        import re
        v = v.strip()
        if not re.match(USERNAME_PATTERN, v):
            raise ValueError("用户名须为 2-20 位字母、数字、下划线或中文")
        return v

    @field_validator("password")
    @classmethod
    def check_password(cls, v: str) -> str:
        if len(v) < 4 or len(v) > 100:
            raise ValueError("密码需 4-100 个字符")
        return v

    @field_validator("invite_code")
    @classmethod
    def check_invite_code(cls, v: str) -> str:
        v = v.strip().upper()
        if not v or len(v) > 32:
            raise ValueError("请填写有效邀请码")
        return v


class LoginBody(BaseModel):
    username: str
    password: str


class ProfileBody(BaseModel):
    nickname: str
    avatar_key: str = "indigo"

    @field_validator("nickname")
    @classmethod
    def check_nickname(cls, value: str) -> str:
        value = value.strip()
        if not value or len(value) > 20:
            raise ValueError("昵称需为 1-20 个字符")
        return value

    @field_validator("avatar_key")
    @classmethod
    def check_avatar_key(cls, value: str) -> str:
        if value not in AVATAR_KEYS:
            raise ValueError("请选择有效的头像")
        return value


class PasswordBody(BaseModel):
    current_password: str
    new_password: str

    @field_validator("new_password")
    @classmethod
    def check_new_password(cls, value: str) -> str:
        if len(value) < 4 or len(value) > 100:
            raise ValueError("新密码需为 4-100 个字符")
        return value


def _public_user(user: dict) -> dict:
    has_custom_avatar = user.get("avatar_key") == "custom" and bool(user.get("avatar_file"))
    return {
        "id": user["id"],
        "username": user["username"],
        "nickname": user.get("nickname") or user["username"],
        "avatar_key": user.get("avatar_key") or "indigo",
        "avatar_url": f"/api/auth/users/{user['id']}/avatar" if has_custom_avatar else "",
    }


def _client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for", "")
    return (forwarded.split(",", 1)[0].strip() if forwarded else
            request.client.host if request.client else "unknown")


@router.post("/register")
def register(body: RegisterBody, request: Request):
    username = body.username.strip()
    pw_hash = auth_module.hash_password(body.password)
    user, status = database.create_user_with_invite(
        username, pw_hash, body.invite_code
    )
    if status == "username_exists":
        bus.log(f"注册失败 · 用户名已存在 · 用户 {username} · IP {_client_ip(request)}", channel="auth", level="warn")
        raise HTTPException(status_code=409, detail="用户名已存在")
    if status == "invalid_invite":
        bus.log(f"注册失败 · 邀请码无效 · 用户 {username} · IP {_client_ip(request)}", channel="auth", level="warn")
        raise HTTPException(status_code=422, detail="邀请码无效、已使用或已作废")
    if not user:
        bus.log(f"注册失败 · 系统错误 · 用户 {username} · IP {_client_ip(request)}", channel="auth", level="error")
        raise HTTPException(status_code=500, detail="注册失败，请重试")
    token = auth_module.create_token(user["id"], user["username"])
    database.record_user_login(user["id"])
    bus.log(f"注册成功 · 用户 {username}#{user['id']} · IP {_client_ip(request)}", channel="auth", level="success")
    return {
        "success": True,
        "message": "注册成功",
        "token": token,
        "user": _public_user(user),
    }


@router.post("/login")
def login(body: LoginBody, request: Request):
    username = body.username.strip()
    user = database.get_user_by_username(username)
    if not user or not auth_module.verify_password(body.password, user["password_hash"]):
        bus.log(f"登录失败 · 用户 {username or '空用户名'} · IP {_client_ip(request)}", channel="auth", level="warn")
        raise HTTPException(status_code=401, detail="用户名或密码错误")
    database.record_user_login(user["id"])
    token = auth_module.create_token(user["id"], user["username"])
    bus.log(f"登录成功 · 用户 {user['username']}#{user['id']} · IP {_client_ip(request)}", channel="auth", level="success")
    return {
        "success": True,
        "message": "登录成功",
        "token": token,
        "user": _public_user(user),
    }


@router.post("/logout")
def logout(
    request: Request,
    user: dict = Depends(auth_module.get_current_user),
):
    bus.log(f"主动退出 · 用户 {user['username']}#{user['user_id']} · IP {_client_ip(request)}", channel="auth", level="info")
    return {"success": True, "message": "已退出"}


@router.get("/me")
def get_me(user: dict = Depends(auth_module.get_current_user)):
    """获取当前用户信息（需要登录）。"""
    db_user = database.get_user_by_id(user["user_id"])
    return {
        "success": True,
        "user": {
            "id": user["user_id"],
            "username": user["username"],
            "nickname": (db_user or {}).get("nickname") or user["username"],
            "avatar_key": (db_user or {}).get("avatar_key") or "indigo",
            "avatar_url": f"/api/auth/users/{user['user_id']}/avatar" if (db_user or {}).get("avatar_key") == "custom" and (db_user or {}).get("avatar_file") else "",
            "created_at": (db_user or {}).get("created_at", ""),
            "is_admin": bool((db_user or {}).get("is_admin")),
            "is_root": user["username"] == "root",
        },
    }


@router.patch("/profile")
@router.post("/profile")
def update_profile(body: ProfileBody, user: dict = Depends(auth_module.get_current_user)):
    if not database.update_user_profile(user["user_id"], body.nickname, body.avatar_key):
        raise HTTPException(status_code=404, detail="用户不存在")
    db_user = database.get_user_by_id(user["user_id"])
    return {"success": True, "message": "昵称已更新", "user": _public_user(db_user)}


@router.post("/avatar")
async def upload_avatar(file: UploadFile = File(...), user: dict = Depends(auth_module.get_current_user)):
    data = await file.read(MAX_AVATAR_SIZE + 1)
    if len(data) > MAX_AVATAR_SIZE:
        raise HTTPException(status_code=413, detail="头像不能超过 2MB")
    if not data.startswith(b"\xff\xd8\xff"):
        raise HTTPException(status_code=415, detail="请上传裁剪后的 JPEG 头像")
    relative = Path(str(user["user_id"])) / "avatar.jpg"
    target = AVATAR_DIR / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(data)
    database.update_user_avatar_file(user["user_id"], str(relative))
    db_user = database.get_user_by_id(user["user_id"])
    return {"success": True, "message": "头像已更新", "user": _public_user(db_user)}


@router.get("/users/{user_id}/avatar")
def user_avatar(user_id: int):
    db_user = database.get_user_by_id(user_id)
    if not db_user or not db_user.get("avatar_file"):
        raise HTTPException(status_code=404, detail="头像不存在")
    target = (AVATAR_DIR / db_user["avatar_file"]).resolve()
    if AVATAR_DIR.resolve() not in target.parents or not target.is_file():
        raise HTTPException(status_code=404, detail="头像不存在")
    return FileResponse(target, media_type="image/jpeg", headers={"Cache-Control": "no-cache"})


@router.post("/password")
def update_password(body: PasswordBody, user: dict = Depends(auth_module.get_current_user)):
    db_user = database.get_user_by_id(user["user_id"])
    if not db_user or not auth_module.verify_password(body.current_password, db_user["password_hash"]):
        raise HTTPException(status_code=422, detail="当前密码不正确")
    if auth_module.verify_password(body.new_password, db_user["password_hash"]):
        raise HTTPException(status_code=422, detail="新密码不能与当前密码相同")
    database.update_user_password(user["user_id"], auth_module.hash_password(body.new_password))
    return {"success": True, "message": "密码已修改"}
