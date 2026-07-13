"""Per-user DeepSeek API configuration."""
from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app import auth as auth_module, database

router = APIRouter(prefix="/api/config", tags=["config"])


class AIConfig(BaseModel):
    deepseek_api_key: str = ""
    deepseek_model: str = ""


def _masked(value: Optional[str], left: int = 6, right: int = 4) -> str:
    value = (value or "").strip()
    if not value:
        return ""
    if len(value) <= left + right:
        return value[:2] + "***"
    return value[:left] + "***" + value[-right:]


@router.get("")
def get_config(user: dict = Depends(auth_module.get_current_user)):
    cfg = database.get_user_config(user["user_id"])
    configured = bool(cfg.get("deepseek_api_key"))
    return {
        "configured": configured,
        "missing": [] if configured else ["deepseek_api_key"],
        "values": {
            "deepseek_api_key_masked": _masked(cfg.get("deepseek_api_key", "")),
            "deepseek_model": cfg.get("deepseek_model", "") or "deepseek-v4-flash",
        },
    }


def _config_values(cfg: AIConfig, user_id: int) -> tuple[str, str]:
    current = database.get_user_config(user_id)
    api_key = cfg.deepseek_api_key.strip() or current.get("deepseek_api_key", "")
    model = (
        cfg.deepseek_model.strip()
        if cfg.deepseek_model.strip() in {"deepseek-v4-flash", "deepseek-v4-pro"}
        else current.get("deepseek_model", "") or "deepseek-v4-flash"
    )
    return api_key, model


@router.post("")
def save_config(cfg: AIConfig, user: dict = Depends(auth_module.get_current_user)):
    api_key, model = _config_values(cfg, user["user_id"])
    database.save_ai_config(user["user_id"], api_key, model)
    return {"success": True, "message": "AI 配置已保存"}
