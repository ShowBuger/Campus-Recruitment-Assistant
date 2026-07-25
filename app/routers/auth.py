"""认证接口：注册、登录、退出、获取当前用户信息。"""
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, field_validator

from app import auth as auth_module, bus, database

router = APIRouter(prefix="/api/auth", tags=["auth"])

USERNAME_PATTERN = r"^[a-zA-Z0-9_一-鿿]{2,20}$"


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
        "user": {"id": user["id"], "username": user["username"]},
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
        "user": {"id": user["id"], "username": user["username"]},
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
            "created_at": (db_user or {}).get("created_at", ""),
            "is_admin": bool((db_user or {}).get("is_admin")),
            "is_root": user["username"] == "root",
        },
    }
