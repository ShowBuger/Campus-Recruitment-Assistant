"""Per-user AI provider configuration."""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator

from app import ai_provider_utils, auth as auth_module, database

router = APIRouter(prefix="/api/config", tags=["config"])


class AIConfig(BaseModel):
    ai_provider: str = "deepseek"
    deepseek_api_key: str = Field(default="", max_length=500)
    deepseek_model: str = Field(default="", max_length=100)
    deepseek_base_url: str = Field(default="", max_length=500)
    openai_api_key: str = Field(default="", max_length=500)
    openai_model: str = Field(default="", max_length=100)
    openai_base_url: str = Field(default="", max_length=500)
    openai_api_mode: str = "responses"
    anthropic_api_key: str = Field(default="", max_length=500)
    anthropic_model: str = Field(default="", max_length=100)
    anthropic_base_url: str = Field(default="", max_length=500)
    apidock_api_key: str = Field(default="", max_length=500)
    apidock_model: str = Field(default="", max_length=100)
    apidock_base_url: str = Field(default="", max_length=500)

    @field_validator("ai_provider")
    @classmethod
    def validate_provider(cls, value: str) -> str:
        value = value.strip().lower()
        if value not in {"deepseek", "openai", "anthropic", "apidock"}:
            raise ValueError("不支持的 AI 服务商")
        return value

    @field_validator("deepseek_model", "openai_model", "anthropic_model", "apidock_model")
    @classmethod
    def validate_model(cls, value: str) -> str:
        value = value.strip()
        if value and (any(ch.isspace() for ch in value) or "/" in value or "\\" in value):
            raise ValueError("模型名称格式不正确")
        return value

    @field_validator("openai_api_mode")
    @classmethod
    def validate_openai_mode(cls, value: str) -> str:
        value = value.strip().lower()
        if value not in {"responses", "chat_completions"}:
            raise ValueError("不支持的 OpenAI 接口协议")
        return value


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
    provider = cfg.get("ai_provider") or "deepseek"
    key_fields = {
        "deepseek": "deepseek_api_key",
        "openai": "openai_api_key",
        "anthropic": "anthropic_api_key",
        "apidock": "apidock_api_key",
    }
    key_field = key_fields.get(provider, "deepseek_api_key")
    configured = bool(cfg.get(key_field))
    return {
        "configured": configured,
        "missing": [] if configured else [key_field],
        "values": {
            "ai_provider": provider,
            "deepseek_api_key_masked": _masked(cfg.get("deepseek_api_key", "")),
            "deepseek_model": cfg.get("deepseek_model", "") or "deepseek-v4-flash",
            "deepseek_base_url": cfg.get("deepseek_base_url", "") or ai_provider_utils.DEFAULT_BASE_URLS["deepseek"],
            "openai_api_key_masked": _masked(cfg.get("openai_api_key", "")),
            "openai_model": cfg.get("openai_model", "") or "gpt-5.4-mini",
            "openai_base_url": cfg.get("openai_base_url", "") or ai_provider_utils.DEFAULT_BASE_URLS["openai"],
            "openai_api_mode": cfg.get("openai_api_mode", "") or "responses",
            "anthropic_api_key_masked": _masked(cfg.get("anthropic_api_key", "")),
            "anthropic_model": cfg.get("anthropic_model", "") or "claude-sonnet-5",
            "anthropic_base_url": cfg.get("anthropic_base_url", "") or ai_provider_utils.DEFAULT_BASE_URLS["anthropic"],
            "apidock_api_key_masked": _masked(cfg.get("apidock_api_key", "")),
            "apidock_model": cfg.get("apidock_model", "") or "gpt-4o",
            "apidock_base_url": cfg.get("apidock_base_url", "") or ai_provider_utils.DEFAULT_BASE_URLS["apidock"],
        },
    }


def _config_values(cfg: AIConfig, user_id: int) -> dict:
    current = database.get_user_config(user_id)
    return {
        "ai_provider": cfg.ai_provider,
        "deepseek_api_key": cfg.deepseek_api_key.strip() or current.get("deepseek_api_key", ""),
        "deepseek_model": cfg.deepseek_model or current.get("deepseek_model", "") or "deepseek-v4-flash",
        "deepseek_base_url": ai_provider_utils.normalize_base_url(
            cfg.deepseek_base_url or current.get("deepseek_base_url", ""), "deepseek"
        ),
        "openai_api_key": cfg.openai_api_key.strip() or current.get("openai_api_key", ""),
        "openai_model": cfg.openai_model or current.get("openai_model", "") or "gpt-5.4-mini",
        "openai_base_url": ai_provider_utils.normalize_base_url(
            cfg.openai_base_url or current.get("openai_base_url", ""), "openai"
        ),
        "openai_api_mode": cfg.openai_api_mode or current.get("openai_api_mode", "") or "responses",
        "anthropic_api_key": cfg.anthropic_api_key.strip() or current.get("anthropic_api_key", ""),
        "anthropic_model": cfg.anthropic_model or current.get("anthropic_model", "") or "claude-sonnet-5",
        "anthropic_base_url": ai_provider_utils.normalize_base_url(
            cfg.anthropic_base_url or current.get("anthropic_base_url", ""), "anthropic"
        ),
        "apidock_api_key": cfg.apidock_api_key.strip() or current.get("apidock_api_key", ""),
        "apidock_model": cfg.apidock_model or current.get("apidock_model", "") or "gpt-4o",
        "apidock_base_url": ai_provider_utils.normalize_base_url(
            cfg.apidock_base_url or current.get("apidock_base_url", ""), "apidock"
        ),
    }


@router.post("")
def save_config(cfg: AIConfig, user: dict = Depends(auth_module.get_current_user)):
    try:
        values = _config_values(cfg, user["user_id"])
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    database.save_ai_config(user["user_id"], values)
    provider_name = {"deepseek": "DeepSeek", "openai": "OpenAI GPT", "anthropic": "Claude"}[cfg.ai_provider]
    return {"success": True, "message": f"已切换并保存 {provider_name} 配置"}


@router.post("/models")
def list_provider_models(cfg: AIConfig, user: dict = Depends(auth_module.get_current_user)):
    try:
        values = _config_values(cfg, user["user_id"])
        provider = cfg.ai_provider
        models = ai_provider_utils.fetch_models(
            provider,
            values[f"{provider}_api_key"],
            values[f"{provider}_base_url"],
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=f"读取模型列表失败：{exc}") from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"无法连接模型服务：{exc}") from exc
    return {"provider": provider, "models": models, "count": len(models)}
