"""飞书配置接口：per-user 读取/保存、测试连接。"""
from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app import auth as auth_module, database, feishu, state

router = APIRouter(prefix="/api/config", tags=["config"])


class FeishuConfig(BaseModel):
    feishu_app_id: str = ""
    feishu_app_secret: str = ""
    feishu_app_token: str = ""
    main_table_id: str = ""
    deepseek_api_key: str = ""
    deepseek_model: str = ""


class TestConfig(FeishuConfig):
    pass


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
    required = ["feishu_app_id", "feishu_app_secret", "feishu_app_token", "main_table_id"]
    missing = [k for k in required if not cfg.get(k)]
    return {
        "configured": not missing,
        "missing": missing,
        "values": {
            "feishu_app_id": cfg.get("feishu_app_id", ""),
            "feishu_app_secret_masked": _masked(cfg.get("feishu_app_secret", "")),
            "feishu_app_token": cfg.get("feishu_app_token", ""),
            "main_table_id": cfg.get("main_table_id", ""),
            "deepseek_api_key_masked": _masked(cfg.get("deepseek_api_key", "")),
            "deepseek_model": cfg.get("deepseek_model", "") or "deepseek-v4-flash",
        },
    }


def _build_payload(cfg: FeishuConfig, user_id: int) -> dict:
    current = database.get_user_config(user_id)
    raw_token = cfg.feishu_app_token.strip()
    app_token = feishu.parse_app_token(raw_token) or current.get("feishu_app_token", "")

    table_id = feishu.parse_table_id(cfg.main_table_id.strip())
    if not table_id and raw_token:
        table_id = feishu.parse_table_id(raw_token)
    if not table_id:
        table_id = current.get("main_table_id", "")

    return {
        "FEISHU_APP_ID": cfg.feishu_app_id.strip() or current.get("feishu_app_id", ""),
        "FEISHU_APP_SECRET": cfg.feishu_app_secret.strip() or current.get("feishu_app_secret", ""),
        "FEISHU_APP_TOKEN": app_token,
        "MAIN_TABLE_ID": table_id,
        "DEEPSEEK_API_KEY": cfg.deepseek_api_key.strip() or current.get("deepseek_api_key", ""),
        "DEEPSEEK_MODEL": (
            cfg.deepseek_model.strip()
            if cfg.deepseek_model.strip() in {"deepseek-v4-flash", "deepseek-v4-pro"}
            else current.get("deepseek_model", "") or "deepseek-v4-flash"
        ),
    }


@router.post("")
def save_config(cfg: FeishuConfig, user: dict = Depends(auth_module.get_current_user)):
    payload = _build_payload(cfg, user["user_id"])
    database.save_user_config(user["user_id"], payload)
    state.set_cache(user["user_id"], {})
    return {"success": True, "message": "飞书配置已保存"}


@router.post("/test")
def test_config(cfg: TestConfig, user: dict = Depends(auth_module.get_current_user)):
    payload = _build_payload(cfg, user["user_id"])
    try:
        feishu.test_config(payload)
        return {"success": True, "message": "连接成功：已能读取飞书主表"}
    except Exception as e:
        return {"success": False, "error": feishu.friendly_error(e)}
