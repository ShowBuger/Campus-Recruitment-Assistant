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
# Rich role profiles are substantially larger than a score-only response.
# Smaller batches prevent one long generation from truncating later jobs.
CHUNK_SIZE = 20
MAX_WORKERS = 3
_RUNS: dict[str, dict] = {}
_RUNS_LOCK = RLock()
_ACTIVE_RUN_IDS: set[str] = set()

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
    base_run_id: str = Field(default="", max_length=64)
    run_mode: str = Field(default="full", pattern="^(full|incremental|refine)$")


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
        "record_id": record["record_id"],
        "company": str(record.get("company") or "")[:200],
        "job": str(record.get("job") or "")[:500],
        # Shared records usually only contain company and job. These optional
        # hints are passed through when present, but ranking must not rely on
        # them being populated.
        "city_hint": str(record.get("city") or "")[:100],
        "direction_hints": record.get("dir") or [],
        "company_type_hint": str(record.get("type") or "")[:100],
        "batch_hint": str(record.get("batch") or "")[:100],
        "deadline": record.get("deadline") or None,
    }


def _string_list(value: object, *, limit: int = 6, item_limit: int = 120) -> list[str]:
    if not isinstance(value, list):
        return []
    return [
        str(item).strip()[:item_limit]
        for item in value[:limit]
        if str(item).strip()
    ]


def _rank_chunk(provider: str, api_key: str, model: str, base_url: str, api_mode: str,
                preference: str, resume_text: str, records: list[dict]) -> list[dict]:
    system = _load_system_prompt()
    content = f"""【候选人岗位偏好】\n{preference or '未填写，请主要根据简历画像判断'}

【候选人结构化画像】\n{resume_text[:6000] if resume_text else '未选择简历，请主要根据岗位偏好判断'}

共享岗位通常只有公司名和岗位名。请充分利用模型对公司业务、岗位族和校招市场的知识，
先为每个岗位构建“推断岗位画像”，再与候选人画像逐项匹配。画像至少考虑：
典型工作内容、可能的技术栈/能力要求、业务场景、学历或专业倾向、成长路径、
常见薪酬福利水平及工作强度风险。

重要：这些不是已核实的招聘 JD。所有推断必须保守；薪资只能给宽泛区间或相对水平，
并标注低/中置信度。公司或岗位含义不明确时直接写“信息不足”，不得编造精确数字、
地点、福利或招聘要求。评分主要依据岗位族与简历中的明确证据，而不是公司知名度。

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
    system = "你是求职简历信息提取助手。只依据简历中的明确事实提取信息，绝不补全或猜测。"
    content = f"""请将以下简历提取为用于岗位匹配的结构化候选人画像。
严格输出 JSON 对象，不要 Markdown。字段固定为：
education（学校、专业、学历、毕业时间）、target_roles、technical_skills、
project_evidence、internship_evidence、domain_experience、achievements、
city_preference、industry_preference、constraints、missing_or_uncertain。

technical_skills、project_evidence、internship_evidence 必须保留“技能/成果 + 对应项目或经历”
的证据关系；只写在技能清单却没有使用证据的，注明“仅技能栏提及”。无法从简历确认的内容
放入 missing_or_uncertain，不能写成已具备。数组字段最多各 8 项，整体不超过 3000 个汉字。

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
                    model: str, resume_used: bool, *, partial: bool = False,
                    seed_items: list[dict] | None = None,
                    prior_evaluated_ids: list[str] | None = None) -> dict:
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
        confidence = str(item.get("profile_confidence") or "low").lower()
        if confidence not in {"medium", "low"}:
            confidence = "low"
        role_profile = {
            "summary": str(item.get("role_summary") or "岗位画像信息不足")[:240],
            "work_content": _string_list(item.get("work_content"), limit=5),
            "likely_requirements": _string_list(item.get("likely_requirements"), limit=6),
            "likely_tech_stack": _string_list(item.get("likely_tech_stack"), limit=8, item_limit=60),
            "business_context": str(item.get("business_context") or "")[:180],
            "compensation": str(item.get("compensation") or "暂无可靠薪酬信息")[:180],
            "work_style_risk": str(item.get("work_style_risk") or "信息不足")[:180],
            "confidence": confidence,
        }
        results.append({
            **record,
            "recommendation_score": score,
            "recommendation_grade": grade if grade in {"S", "A", "B", "C"} else "C",
            "recommendation_reason": str(item.get("reason") or "模型未给出理由")[:160],
            "match_strengths": _string_list(item.get("match_strengths"), limit=4),
            "match_gaps": _string_list(item.get("match_gaps"), limit=4),
            "ai_role_profile": role_profile,
        })
    if seed_items:
        seen = {item["record_id"] for item in results}
        results.extend(item for item in seed_items if item.get("record_id") not in seen)
    results.sort(key=lambda item: -item["recommendation_score"])
    limit = int(cfg.get("recommendation_limit") or 0)
    if limit > 0:
        results = results[:limit]
    return {"success": True, "items": results, "scanned": len(records),
            "evaluated_record_ids": list(dict.fromkeys(
                [*(prior_evaluated_ids or []), *(item["record_id"] for item in records)]
            )),
            "resume_used": resume_used, "resume_summarized": resume_used, "partial": partial,
            "provider": provider, "provider_name": PROVIDER_NAMES[provider], "model": model}


def _finish_ranking(run_id: str, *, user_id: int, cfg: dict, provider: str, api_key: str,
                    model: str, base_url: str, api_mode: str, preference: str,
                    resume_text: str, records: list[dict], seed_items: list[dict] | None = None,
                    prior_evaluated_ids: list[str] | None = None) -> None:
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
            failed = 0
            for future in as_completed(futures):
                try:
                    for item in future.result():
                        record_id = str(item.get("record_id") or "")
                        if record_id:
                            ranked[record_id] = item
                except Exception:
                    # One malformed or timed-out AI batch must not discard all
                    # successfully completed batches.
                    failed += 1
                completed += 1
                _set_run(run_id, completed_chunks=completed,
                         message=f"已处理 {completed} / {len(chunks)} 个岗位批次"
                                 + (f"，{failed} 批失败" if failed else ""),
                         result=_result_payload(records, ranked, cfg, provider, model, bool(resume_text),
                                                partial=True, seed_items=seed_items,
                                                prior_evaluated_ids=prior_evaluated_ids))

        result = _result_payload(records, ranked, cfg, provider, model, bool(resume_text),
                                 seed_items=seed_items, prior_evaluated_ids=prior_evaluated_ids)
        result["failed_chunks"] = failed
        _set_run(run_id, status="finished", phase="finished",
                 message="筛选完成" if not failed else f"筛选完成，{failed} 个批次未能返回",
                 result=result)
    except Exception as exc:
        _set_run(run_id, status="failed", phase="failed", message=str(exc))


def _run_persisted_recommendation(run_id: str, user_id: int) -> None:
    try:
        run = database.get_recommendation_run(user_id, run_id)
        if not run or run.get("status") != "running":
            return
        cfg = database.get_user_config(user_id)
        provider = str(run.get("provider") or cfg.get("ai_provider") or "deepseek")
        if provider not in PROVIDER_NAMES:
            raise ValueError("筛选任务的 AI 服务商配置已失效")
        api_key = str(cfg.get(f"{provider}_api_key") or "")
        if not api_key:
            raise ValueError(f"请先配置 {PROVIDER_NAMES[provider]} API Key")
        model = str(run.get("model") or cfg.get("recommendation_model") or "").strip()
        if not model:
            raise ValueError("筛选任务的推荐模型配置已失效")
        resume_text = ""
        resume_filename = str(run.get("resume_filename") or "").strip()
        if resume_filename:
            path = _user_resume_path(user_id, resume_filename)
            if not path.is_file():
                raise ValueError("筛选任务关联的简历已不存在")
            resume_text = _extract_resume_text(path)
        all_records = [
            item for item in local_records.list_shared_records(user_id)
            if not local_records.is_shared_deadline_expired(item.get("deadline"))
        ]
        records, seed_items, prior_evaluated_ids = _select_run_records(
            user_id, run, all_records
        )
        _set_run(run_id, phase="preparing", message="正在恢复并准备岗位数据…",
                 scanned=len(records), total_chunks=0, completed_chunks=0)
        _finish_ranking(
            run_id, user_id=user_id, cfg=cfg, provider=provider, api_key=api_key,
            model=model,
            base_url=cfg.get(f"{provider}_base_url") or ai_provider_utils.DEFAULT_BASE_URLS[provider],
            api_mode=cfg.get("openai_api_mode") or "responses",
            preference=str(run.get("preference") or ""), resume_text=resume_text, records=records,
            seed_items=seed_items, prior_evaluated_ids=prior_evaluated_ids,
        )
    except Exception as exc:
        _set_run(run_id, status="failed", phase="failed", message=str(exc))
    finally:
        with _RUNS_LOCK:
            _ACTIVE_RUN_IDS.discard(run_id)


def _launch_persisted_run(run_id: str, user_id: int) -> bool:
    with _RUNS_LOCK:
        if run_id in _ACTIVE_RUN_IDS:
            return False
        _ACTIVE_RUN_IDS.add(run_id)
    Thread(target=_run_persisted_recommendation, args=(run_id, user_id), daemon=True).start()
    return True


def recover_recommendation_runs() -> int:
    """Resume database-backed tasks after an application worker restart."""
    recovered = 0
    for run in database.list_running_recommendation_runs():
        run_id, user_id = str(run["id"]), int(run["user_id"])
        cached = database.get_recommendation_run(user_id, run_id) or {}
        cached["user_id"] = user_id
        with _RUNS_LOCK:
            _RUNS[run_id] = cached
        if _launch_persisted_run(run_id, user_id):
            recovered += 1
    return recovered


def _select_run_records(user_id: int, run: dict, all_records: list[dict]) -> tuple[list[dict], list[dict] | None, list[str]]:
    """Resolve the immutable input set represented by a full, incremental or refine run."""
    mode = str(run.get("run_mode") or "full")
    if mode == "full":
        return all_records, None, []
    base = database.get_recommendation_run(user_id, str(run.get("base_run_id") or ""))
    if not base or base.get("status") != "finished":
        raise ValueError("所选筛选历史不存在或尚未完成")
    base_result = base.get("result") or {}
    base_items = base_result.get("items") or []
    prior_ids = list(base_result.get("evaluated_record_ids") or [])
    if mode == "refine":
        allowed = {item.get("record_id") for item in base_items}
        return [item for item in all_records if item["record_id"] in allowed], None, []
    if prior_ids:
        evaluated = set(prior_ids)
        records = [item for item in all_records if item["record_id"] not in evaluated]
    else:
        cutoff = str(base.get("created_at") or "")
        records = [item for item in all_records if str(item.get("created_at") or "") > cutoff]
    return records, base_items, prior_ids


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
    all_records = [
        item for item in local_records.list_shared_records(user["user_id"])
        if not local_records.is_shared_deadline_expired(item.get("deadline"))
    ]
    records = all_records
    if request.run_mode != "full":
        if not request.base_run_id:
            raise HTTPException(status_code=422, detail="请选择一条筛选历史")
        base_run = database.get_recommendation_run(user["user_id"], request.base_run_id)
        if not base_run or base_run.get("status") != "finished":
            raise HTTPException(status_code=404, detail="所选筛选历史不存在或尚未完成")
        records, _, _ = _select_run_records(user["user_id"], {
            "run_mode": request.run_mode, "base_run_id": request.base_run_id,
        }, all_records)
    run_id = uuid4().hex
    run = {"id": run_id, "user_id": user["user_id"], "status": "running", "phase": "preparing",
           "message": "正在准备岗位数据…", "total_chunks": 0, "completed_chunks": 0,
           "preference": request.preference.strip(), "resume_filename": request.resume_filename.strip(),
           "provider": provider, "model": model, "scanned": len(records),
           "base_run_id": request.base_run_id, "run_mode": request.run_mode}
    if not database.create_recommendation_run(run):
        raise HTTPException(status_code=409, detail="已有智能筛选任务正在进行，请等待完成")
    with _RUNS_LOCK:
        _RUNS[run_id] = run.copy()
    _launch_persisted_run(run_id, user["user_id"])
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
