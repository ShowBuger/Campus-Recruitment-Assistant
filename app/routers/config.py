"""Per-user AI provider configuration."""
import json
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
    kimi_api_key: str = Field(default="", max_length=500)
    kimi_model: str = Field(default="", max_length=100)
    kimi_base_url: str = Field(default="", max_length=500)

    @field_validator("ai_provider")
    @classmethod
    def validate_provider(cls, value: str) -> str:
        value = value.strip().lower()
        if value not in {"deepseek", "openai", "anthropic", "kimi"}:
            raise ValueError("不支持的 AI 服务商")
        return value

    @field_validator("deepseek_model", "openai_model", "anthropic_model", "kimi_model")
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


class RecommendationConfig(BaseModel):
    recommendation_limit: int = Field(default=12, ge=0, le=5000)
    recommendation_min_score: int = Field(default=45, ge=0, le=95)
    recommendation_model: str = Field(default="", max_length=100)


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
        "kimi": "kimi_api_key",
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
            "kimi_api_key_masked": _masked(cfg.get("kimi_api_key", "")),
            "kimi_model": cfg.get("kimi_model", "") or "kimi-k3",
            "kimi_base_url": cfg.get("kimi_base_url", "") or ai_provider_utils.DEFAULT_BASE_URLS["kimi"],
        },
    }


@router.get("/recommendation")
def get_recommendation_config(user: dict = Depends(auth_module.get_current_user)):
    cfg = database.get_user_config(user["user_id"])
    return {
        "recommendation_limit": int(cfg.get("recommendation_limit") if cfg.get("recommendation_limit") is not None else 12),
        "recommendation_min_score": int(cfg.get("recommendation_min_score") or 45),
        "recommendation_model": str(cfg.get("recommendation_model") or ""),
        "ai_provider": cfg.get("ai_provider") or "deepseek",
        "ai_model": cfg.get(f"{cfg.get('ai_provider') or 'deepseek'}_model") or "",
    }


@router.post("/recommendation")
def save_recommendation_config(
    config: RecommendationConfig,
    user: dict = Depends(auth_module.get_current_user),
):
    with database._write_lock:
        db = database.get_db()
        db.execute(
            """UPDATE user_configs
               SET recommendation_limit = ?, recommendation_min_score = ?, recommendation_model = ?
               WHERE user_id = ?""",
            (config.recommendation_limit, config.recommendation_min_score, config.recommendation_model.strip(), user["user_id"]),
        )
        db.commit()
    return {"success": True, "message": "岗位推荐配置已保存"}


@router.get("/recommendation/models")
def get_recommendation_models(user: dict = Depends(auth_module.get_current_user)):
    cfg = database.get_user_config(user["user_id"])
    provider = cfg.get("ai_provider") or "deepseek"
    api_key = cfg.get(f"{provider}_api_key") or ""
    model = cfg.get(f"{provider}_model") or ""
    if not api_key:
        raise HTTPException(status_code=422, detail="请先在 AI 配置中保存当前服务商的 API Key")
    try:
        models = ai_provider_utils.fetch_models(
            provider, api_key,
            cfg.get(f"{provider}_base_url") or ai_provider_utils.DEFAULT_BASE_URLS[provider],
        )
    except (ValueError, RuntimeError) as exc:
        raise HTTPException(status_code=502, detail=f"读取当前服务商模型失败：{exc}") from exc
    if model and model not in models:
        models.insert(0, model)
    return {"provider": provider, "models": models, "current_model": model}


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
        "kimi_api_key": cfg.kimi_api_key.strip() or current.get("kimi_api_key", ""),
        "kimi_model": cfg.kimi_model or current.get("kimi_model", "") or "kimi-k3",
        "kimi_base_url": ai_provider_utils.normalize_base_url(
            cfg.kimi_base_url or current.get("kimi_base_url", ""), "kimi"
        ),
    }


@router.post("")
def save_config(cfg: AIConfig, user: dict = Depends(auth_module.get_current_user)):
    try:
        values = _config_values(cfg, user["user_id"])
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    database.save_ai_config(user["user_id"], values)
    provider_name = {
        "deepseek": "DeepSeek", "openai": "OpenAI GPT",
        "anthropic": "Claude", "kimi": "Kimi",
    }[cfg.ai_provider]
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
    with database._write_lock:
        db = database.get_db()
        db.execute(
            """INSERT INTO ai_model_cache (user_id, provider, models_json, updated_at)
               VALUES (?, ?, ?, datetime('now'))
               ON CONFLICT(user_id, provider) DO UPDATE SET
               models_json=excluded.models_json, updated_at=datetime('now')""",
            (user["user_id"], provider, json.dumps(models, ensure_ascii=False)),
        )
        db.commit()
    return {"provider": provider, "models": models, "count": len(models)}


@router.post("/test")
def test_provider(cfg: AIConfig, user: dict = Depends(auth_module.get_current_user)):
    try:
        values = _config_values(cfg, user["user_id"])
        provider = cfg.ai_provider
        api_key = values[f"{provider}_api_key"]
        if not api_key:
            raise ValueError("请先填写或保存 API Key")
        from app.routers.ai import _call_ai_provider
        output = _call_ai_provider(
            provider,
            api_key,
            values[f"{provider}_model"],
            "你是连接测试器。只回复 OK，不要输出其他内容。",
            "回复 OK",
            base_url=values[f"{provider}_base_url"],
            api_mode=values.get("openai_api_mode", "responses"),
            max_output_tokens=32,
        )
        if not str(output or "").strip():
            raise RuntimeError("模型返回了空响应")
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"AI 连接测试失败：{exc}") from exc
    provider_name = {
        "deepseek": "DeepSeek", "openai": "OpenAI GPT",
        "anthropic": "Claude", "kimi": "Kimi",
    }[provider]
    return {
        "success": True,
        "message": f"{provider_name} 连接正常，模型可用",
        "provider": provider,
        "model": values[f"{provider}_model"],
    }
