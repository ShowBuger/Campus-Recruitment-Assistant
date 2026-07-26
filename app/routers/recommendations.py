"""LLM-backed shared-job recommendations."""
from __future__ import annotations

import json
import re
from threading import RLock, Thread
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app import ai_provider_utils, auth as auth_module, database, local_records
from app.routers.ai import PROVIDER_NAMES, _call_ai_provider, _extract_resume_text, _user_resume_path

router = APIRouter(prefix="/api/recommendations", tags=["recommendations"])
CHUNK_SIZE = 45
MAX_WORKERS = 3
_RUNS: dict[str, dict] = {}
_RUNS_LOCK = RLock()

SKILL_PATH = Path(__file__).resolve().parents[2] / "skills" / "job-recommendation" / "SKILL.md"
_SYSTEM_PROMPT: str | None = None


def _load_system_prompt() -> str:
    global _SYSTEM_PROMPT
    if _SYSTEM_PROMPT is not None:
        return _SYSTEM_PROMPT
    if SKILL_PATH.is_file():
        _SYSTEM_PROMPT = SKILL_PATH.read_text(encoding="utf-8")
        return _SYSTEM_PROMPT
    # Fallback inline prompt when skill file is missing
    _SYSTEM_PROMPT = """你是严谨的校招岗位推荐助手。只能基于候选人偏好、简历和给定岗位信息判断，不能编造事实。
对每一个输入岗位都给出匹配评分。仅输出 JSON 数组，不要 Markdown 或解释。每项严格为：
{"record_id":"...","score":0-100,"grade":"S|A|B|C","reason":"不超过40字的具体匹配或不足原因"}
S=强烈推荐，A=优先推荐，B=值得关注，C=备选。"""
    return _SYSTEM_PROMPT


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
    system = _load_system_prompt()
    content = f"""【候选人岗位偏好】\n{preference or '未填写，请主要根据简历与岗位判断'}

【候选人简历】\n{resume_text[:18000] if resume_text else '未选择简历，请主要根据岗位偏好判断'}

【待评估岗位】\n{json.dumps([_candidate(item) for item in records], ensure_ascii=False)}"""
    return _json_array(_call_ai_provider(
        provider, api_key, model, system, content, base_url=base_url,
        api_mode=api_mode, max_output_tokens=7000,
    ))


def _summarize_resume(provider: str, api_key: str, model: str, base_url: str, api_mode: str,
                      resume_text: str) -> str:
    """Create one compact profile so every ranking request does not carry the full resume."""
    if not resume_text:
        return ""
    system = "你是求职简历信息提取助手。只依据给出的简历提取事实，不要编造。"
    content = f"""请将以下简历压缩为用于岗位匹配的结构化摘要，使用简短中文并保留：
教育背景、求职方向、核心技能、项目/实习、行业偏好、城市偏好、限制条件。
总长度不超过 2500 个汉字；没有的信息写“未提及”。

【简历】
{resume_text[:18000]}"""
    return _call_ai_provider(
        provider, api_key, model, system, content, base_url=base_url,
        api_mode=api_mode, max_output_tokens=1400,
    )[:6000]


def _set_run(run_id: str, **values) -> None:
    with _RUNS_LOCK:
        if run_id in _RUNS:
            _RUNS[run_id].update(values)
    database.update_recommendation_run(run_id, values)


def _result_payload(records: list[dict], ranked: dict[str, dict], cfg: dict, provider: str,
                    model: str, resume_used: bool, *, partial: bool = False) -> dict:
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
            "resume_used": resume_used, "resume_summarized": resume_used, "partial": partial,
            "provider": provider, "provider_name": PROVIDER_NAMES[provider], "model": model}


def _finish_ranking(run_id: str, *, user_id: int, cfg: dict, provider: str, api_key: str,
                    model: str, base_url: str, api_mode: str, preference: str,
                    resume_text: str, records: list[dict]) -> None:
    try:
        resume_profile = ""
        if resume_text:
            _set_run(run_id, phase="summarizing", message="正在提炼简历匹配要点…")
            resume_profile = _summarize_resume(provider, api_key, model, base_url, api_mode, resume_text)

        chunks = [records[index:index + CHUNK_SIZE] for index in range(0, len(records), CHUNK_SIZE)]
        _set_run(run_id, phase="ranking", total_chunks=len(chunks), completed_chunks=0,
                 message="正在分批评估岗位匹配度…")
        ranked: dict[str, dict] = {}
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            futures = {
                executor.submit(_rank_chunk, provider, api_key, model, base_url, api_mode,
                                preference, resume_profile, chunk): chunk
                for chunk in chunks
            }
            completed = 0
            for future in as_completed(futures):
                for item in future.result():
                    record_id = str(item.get("record_id") or "")
                    if record_id:
                        ranked[record_id] = item
                completed += 1
                _set_run(run_id, completed_chunks=completed,
                         message=f"已完成 {completed} / {len(chunks)} 个岗位批次",
                         result=_result_payload(records, ranked, cfg, provider, model, bool(resume_text), partial=True))

        result = _result_payload(records, ranked, cfg, provider, model, bool(resume_text))
        _set_run(run_id, status="finished", phase="finished", message="筛选完成",
                 result=result)
    except Exception as exc:
        _set_run(run_id, status="failed", phase="failed", message=str(exc))


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
    run_id = uuid4().hex
    run = {"id": run_id, "user_id": user["user_id"], "status": "running", "phase": "preparing",
           "message": "正在准备岗位数据…", "total_chunks": 0, "completed_chunks": 0,
           "preference": request.preference.strip(), "resume_filename": request.resume_filename.strip(),
           "provider": provider, "model": model, "scanned": len(records)}
    with _RUNS_LOCK:
        _RUNS[run_id] = run.copy()
    database.create_recommendation_run(run)
    Thread(target=_finish_ranking, kwargs={
        "run_id": run_id, "user_id": user["user_id"], "cfg": cfg, "provider": provider,
        "api_key": api_key, "model": model, "base_url": base_url, "api_mode": api_mode,
        "preference": request.preference.strip(), "resume_text": resume_text, "records": records,
    }, daemon=True).start()
    return {"run_id": run_id, "status": "running", "scanned": len(records)}


@router.get("/history")
def list_recommendation_history(user: dict = Depends(auth_module.get_current_user)):
    return {"items": database.list_recommendation_runs(user["user_id"])}


@router.get("/history/{run_id}")
def get_recommendation_history(run_id: str, user: dict = Depends(auth_module.get_current_user)):
    run = database.get_recommendation_run(user["user_id"], run_id)
    if not run:
        raise HTTPException(status_code=404, detail="未找到该筛选历史")
    return run


@router.delete("/history/{run_id}")
def delete_recommendation_history(run_id: str, user: dict = Depends(auth_module.get_current_user)):
    if not database.delete_recommendation_run(user["user_id"], run_id):
        raise HTTPException(status_code=404, detail="未找到该筛选历史")
    with _RUNS_LOCK:
        run = _RUNS.get(run_id)
        if run and run.get("user_id") == user["user_id"]:
            _RUNS.pop(run_id, None)
    return {"ok": True, "message": "筛选历史已删除"}


@router.get("/{run_id}")
def get_recommendation_run(run_id: str, user: dict = Depends(auth_module.get_current_user)):
    with _RUNS_LOCK:
        run = _RUNS.get(run_id)
        if run and run.get("user_id") == user["user_id"]:
            return {key: value for key, value in run.items() if key != "user_id"}
    run = database.get_recommendation_run(user["user_id"], run_id)
    if not run:
        raise HTTPException(status_code=404, detail="未找到该筛选任务")
    return run
