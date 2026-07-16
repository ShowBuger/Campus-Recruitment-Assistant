"""JWT 认证：注册、登录、token 签发/验证、FastAPI 依赖注入。"""
import os
import secrets
from datetime import datetime, timedelta, timezone
from pathlib import Path

import bcrypt
import jwt
from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app import database

# JWT 密钥：优先读 .env 中的 JWT_SECRET，没有则首次自动生成并写入 .env
ENV_PATH = Path(__file__).parent.parent / ".env"


def _get_or_create_jwt_secret() -> str:
    """从 .env 读取 JWT_SECRET，没有则生成一个随机密钥写入。"""
    secret = os.getenv("JWT_SECRET", "")
    if secret:
        return secret
    # 尝试从 .env 文件读取
    if ENV_PATH.exists():
        for line in ENV_PATH.read_text(encoding="utf-8").splitlines():
            if line.startswith("JWT_SECRET="):
                val = line.split("=", 1)[1].strip()
                if val:
                    os.environ["JWT_SECRET"] = val
                    return val
    # 生成新密钥并追加到 .env
    new_secret = secrets.token_urlsafe(32)
    with open(ENV_PATH, "a", encoding="utf-8", newline="\n") as f:
        f.write(f"\nJWT_SECRET={new_secret}\n")
    os.environ["JWT_SECRET"] = new_secret
    return new_secret


JWT_SECRET = _get_or_create_jwt_secret()
JWT_EXPIRE_HOURS = 72

security = HTTPBearer(auto_error=False)


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(password.encode(), password_hash.encode())


def create_token(user_id: int, username: str) -> str:
    payload = {
        "user_id": user_id,
        "username": username,
        "exp": datetime.now(timezone.utc) + timedelta(hours=JWT_EXPIRE_HOURS),
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm="HS256")


def verify_token(token: str) -> dict | None:
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
    except jwt.PyJWTError:
        return None


async def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
) -> dict:
    """FastAPI 依赖：从 Authorization header 或 ?token= 查询参数解析 JWT。"""
    token = None
    if credentials and credentials.credentials:
        token = credentials.credentials
    else:
        token = request.query_params.get("token")
    if not token:
        raise HTTPException(status_code=401, detail="请先登录")
    payload = verify_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="登录已过期，请重新登录")
    db_user = database.get_user_by_id(payload["user_id"])
    if not db_user or db_user["username"] != payload["username"]:
        raise HTTPException(status_code=401, detail="账号不存在或已被删除")
    database.touch_user_last_seen(db_user["id"])
    return {
        "user_id": db_user["id"],
        "username": db_user["username"],
        "is_admin": bool(db_user.get("is_admin")),
        "is_root": db_user["username"] == "root",
    }


def get_optional_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
) -> dict | None:
    """可选认证：不强制要求登录，有 token 就解析。"""
    token = None
    if credentials and credentials.credentials:
        token = credentials.credentials
    else:
        token = request.query_params.get("token")
    if not token:
        return None
    payload = verify_token(token)
    if not payload:
        return None
    db_user = database.get_user_by_id(payload["user_id"])
    if not db_user or db_user["username"] != payload["username"]:
        return None
    database.touch_user_last_seen(db_user["id"])
    return {
        "user_id": db_user["id"],
        "username": db_user["username"],
        "is_admin": bool(db_user.get("is_admin")),
        "is_root": db_user["username"] == "root",
    }
