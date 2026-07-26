"""LLM-backed shared-job recommendations."""
from __future__ import annotations

import json
import re
from concurrent.futures import ThreadPoolExecutor, as_completed

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app import ai_provider_utils, auth as auth_module, database, local_records
from app.routers.ai import PROVIDER_NAMES, _call_ai_provider, _extract_resume_text, _user_resume_path

router = APIRouter(prefix="/api/recommendations", tags=["recommendations"])
CHUNK_SIZE = 45


class RecommendationRequest(BaseModel):
    preference: str = Field(default="", max_length=2000)
    resume_filename: str = Field(default="", max_length=255)


def _json_array(text: str) -> list[dict]:
    text = (text or "").strip()
    if "```" in text:
        text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.I)
    start, end = text.find("["), text.rfind("]")
    if start < 0 or end < start:
        raise ValueError("模型未返回 JSON 数组")
    data = json.loads(text[start:end + 1])
    if not isinstance(data, list):
        raise ValueError("模型返回的推荐结果格式不正确")
    return [item for item in data if isinstance(item, dict)]


def _candidate(record: dict) -> dict:
    return {
        "record_id": record["record_id"], "company": record.get("company") or "",
        "job": str(record.get("job") or "")[:500], "city": record.get("city") or "",
        "directions": record.get("dir") or [], "company_type": record.get("type") or "",
        "deadline": record.get("deadline") or None,
    }


def _rank_chunk(provider: str, api_key: str, model: str, base_url: str, api_mode: str,
                preference: str, resume_text: str, records: list[dict]) -> list[dict]:
    system = """你是严谨的校招岗位推荐助手。只能基于候选人偏好、简历和给定岗位信息判断，不能编造事实。
对每一个输入岗位都给出匹配评分。仅输出 JSON 数组，不要 Markdown 或解释。每项严格为：
{"record_id":"...","score":0-100,"grade":"S|A|B|C","reason":"不超过40字的具体匹配或不足原因"}
S=强烈推荐，A=优先推荐，B=值得关注，C=备选。"""
    content = f"""【候选人岗位偏好】\n{preference or '未填写，请主要根据简历与岗位判断'}

【候选人简历】\n{resume_text[:18000] if resume_text else '未选择简历，请主要根据岗位偏好判断'}

【待评估岗位】\n{json.dumps([_candidate(item) for item in records], ensure_ascii=False)}"""
    return _json_array(_call_ai_provider(
        provider, api_key, model, system, content, base_url=base_url,
        api_mode=api_mode, max_output_tokens=7000,
    ))


@router.post("")
def recommend_jobs(request: RecommendationRequest, user: dict = Depends(auth_module.get_current_user)):
    resume_text = ""
    if request.resume_filename.strip():
        path = _user_resume_path(user["user_id"], request.resume_filename.strip())
        if not path.is_file():
            raise HTTPException(status_code=404, detail="所选简历不存在")
        resume_text = _extract_resume_text(path)
    if not request.preference.strip() and not resume_text:
        raise HTTPException(status_code=422, detail="请填写岗位偏好或选择一份简历")

    cfg = database.get_user_config(user["user_id"])
    provider = cfg.get("ai_provider") or "deepseek"
    if provider not in PROVIDER_NAMES:
        provider = "deepseek"
    api_key = cfg.get(f"{provider}_api_key") or ""
    if not api_key:
        raise HTTPException(status_code=400, detail=f"请先在 AI 配置中填写 {PROVIDER_NAMES[provider]} API Key")
    model = str(cfg.get("recommendation_model") or cfg.get(f"{provider}_model") or "").strip()
    if not model:
        raise HTTPException(status_code=422, detail="请先在设置的岗位推荐页选择模型")
    base_url = cfg.get(f"{provider}_base_url") or ai_provider_utils.DEFAULT_BASE_URLS[provider]
    api_mode = cfg.get("openai_api_mode") or "responses"
    records = [
        item for item in local_records.list_shared_records(user["user_id"])
        if not local_records.is_shared_deadline_expired(item.get("deadline"))
    ]
    chunks = [records[index:index + CHUNK_SIZE] for index in range(0, len(records), CHUNK_SIZE)]
    ranked: dict[str, dict] = {}
    try:
        with ThreadPoolExecutor(max_workers=3) as executor:
            futures = {
                executor.submit(_rank_chunk, provider, api_key, model, base_url, api_mode,
                                request.preference.strip(), resume_text, chunk): chunk
                for chunk in chunks
            }
            for future in as_completed(futures):
                for item in future.result():
                    record_id = str(item.get("record_id") or "")
                    if record_id:
                        ranked[record_id] = item
    except HTTPException:
        raise
    except (ValueError, TypeError, KeyError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=502, detail=f"{PROVIDER_NAMES[provider]} 返回的推荐格式异常：{exc}") from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"调用 {PROVIDER_NAMES[provider]} 推荐失败：{exc}") from exc

    minimum = int(cfg.get("recommendation_min_score") or 45)
    results = []
    for record in records:
        item = ranked.get(record["record_id"])
        if not item:
            continue
        score = max(0, min(100, int(item.get("score") or 0)))
        if score < minimum:
            continue
        grade = str(item.get("grade") or "C").upper()
        results.append({**record, "recommendation_score": score,
                        "recommendation_grade": grade if grade in {"S", "A", "B", "C"} else "C",
                        "recommendation_reason": str(item.get("reason") or "模型未给出理由")[:120]})
    results.sort(key=lambda item: -item["recommendation_score"])
    limit = int(cfg.get("recommendation_limit") or 0)
    if limit > 0:
        results = results[:limit]
    return {"success": True, "items": results, "scanned": len(records),
            "resume_used": bool(resume_text), "method": "大模型语义匹配",
            "provider": provider, "provider_name": PROVIDER_NAMES[provider], "model": model}
