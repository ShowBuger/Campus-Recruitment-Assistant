"""认证接口：注册、登录、获取当前用户信息。"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, field_validator

from app import auth as auth_module, database

router = APIRouter(prefix="/api/auth", tags=["auth"])

USERNAME_PATTERN = r"^[a-zA-Z0-9_一-鿿]{2,20}$"


class RegisterBody(BaseModel):
    username: str
    password: str

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


class LoginBody(BaseModel):
    username: str
    password: str


@router.post("/register")
def register(body: RegisterBody):
    username = body.username.strip()
    existing = database.get_user_by_username(username)
    if existing:
        raise HTTPException(status_code=409, detail="用户名已存在")
    pw_hash = auth_module.hash_password(body.password)
    user = database.create_user(username, pw_hash)
    if not user:
        raise HTTPException(status_code=500, detail="注册失败，请重试")
    token = auth_module.create_token(user["id"], user["username"])
    return {
        "success": True,
        "message": "注册成功",
        "token": token,
        "user": {"id": user["id"], "username": user["username"]},
    }


@router.post("/login")
def login(body: LoginBody):
    username = body.username.strip()
    user = database.get_user_by_username(username)
    if not user or not auth_module.verify_password(body.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="用户名或密码错误")
    token = auth_module.create_token(user["id"], user["username"])
    return {
        "success": True,
        "message": "登录成功",
        "token": token,
        "user": {"id": user["id"], "username": user["username"]},
    }


@router.get("/me")
def get_me(user: dict = __import__("fastapi").Depends(auth_module.get_current_user)):
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
