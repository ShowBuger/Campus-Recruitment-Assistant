"""Deterministic and AI-assisted deduplication for shared-job synchronization."""
from __future__ import annotations

import json
import re
import unicodedata
from difflib import SequenceMatcher
from pathlib import Path
from typing import Callable
from urllib.parse import urlsplit, urlunsplit

from app import ai_provider_utils, database
from app.routers.ai import _call_ai_provider

SKILL_PATH = Path(__file__).resolve().parents[1] / "skills" / "shared-job-deduplication" / "SKILL.md"
COMPANY_SIMILARITY_THRESHOLD = 0.65
AI_BATCH_SIZE = 20
MAX_SIMILAR_RECORDS = 5

_COMPANY_SUFFIXES = (
    "股份有限公司", "有限责任公司", "有限公司", "集团股份", "集团公司", "集团",
    "科技股份", "科技公司", "公司", "co.,ltd.", "co.ltd.", "limited", "ltd.",
)


def _value(record: dict, plain: str, source: str, default=""):
    return record.get(plain) if plain in record else record.get(source, default)


def normalize_company(value: str) -> str:
    text = unicodedata.normalize("NFKC", str(value or "")).casefold()
    text = re.sub(r"[（(][^()（）]{0,20}[)）]", "", text)
    text = re.sub(r"[\s·•・_\-—,，.。/\\]+", "", text)
    changed = True
    while changed:
        changed = False
        for suffix in _COMPANY_SUFFIXES:
            normalized = re.sub(r"[\s,.\-]+", "", suffix.casefold())
            if text.endswith(normalized) and len(text) > len(normalized) + 1:
                text = text[:-len(normalized)]
                changed = True
                break
    return text


def company_similarity(left: str, right: str) -> float:
    a, b = normalize_company(left), normalize_company(right)
    if not a or not b:
        return 0.0
    if a == b:
        return 1.0
    if min(len(a), len(b)) >= 4 and (a in b or b in a):
        return min(len(a), len(b)) / max(len(a), len(b))
    return SequenceMatcher(None, a, b).ratio()


def _batch(record: dict) -> str:
    return unicodedata.normalize("NFKC", str(_value(record, "batch", "批次", "秋招") or "秋招")).strip().casefold()


def _job(record: dict) -> str:
    return unicodedata.normalize("NFKC", str(_value(record, "job", "秋招岗位") or "")).strip().casefold()


def _url(record: dict) -> str:
    raw = str(_value(record, "url", "投递链接") or "").strip()
    if not raw:
        return ""
    try:
        parts = urlsplit(raw)
        return urlunsplit((parts.scheme.casefold(), parts.netloc.casefold(), parts.path, parts.query, parts.fragment))
    except ValueError:
        return raw


def _company(record: dict) -> str:
    return str(_value(record, "company", "公司名称") or "").strip()


def _record_payload(record: dict) -> dict:
    directions = _value(record, "dir", "嵌入式方向", []) or []
    return {
        "record_id": str(record.get("record_id") or record.get("id") or ""),
        "company": _company(record),
        "batch": str(_value(record, "batch", "批次", "秋招") or "秋招"),
        "job": str(_value(record, "job", "秋招岗位") or ""),
        "url": str(_value(record, "url", "投递链接") or ""),
        "city": str(_value(record, "city", "城市") or ""),
        "directions": directions if isinstance(directions, list) else [str(directions)],
    }


def _json_array(text: str) -> list[dict]:
    cleaned = str(text or "").strip()
    fenced = re.search(r"```(?:json)?\s*([\s\S]*?)```", cleaned, re.I)
    if fenced:
        cleaned = fenced.group(1).strip()
    start, end = cleaned.find("["), cleaned.rfind("]")
    if start < 0 or end < start:
        raise ValueError("AI 判重结果不是 JSON 数组")
    value = json.loads(cleaned[start:end + 1])
    if not isinstance(value, list):
        raise ValueError("AI 判重结果格式错误")
    return [item for item in value if isinstance(item, dict)]


def _ai_config(user_id: int) -> dict | None:
    cfg = database.get_user_config(user_id)
    provider = str(cfg.get("ai_provider") or "deepseek")
    api_key = str(cfg.get(f"{provider}_api_key") or "")
    model = str(cfg.get(f"{provider}_model") or "")
    if not api_key or not model or provider not in ai_provider_utils.DEFAULT_BASE_URLS:
        return None
    return {
        "provider": provider, "api_key": api_key, "model": model,
        "base_url": cfg.get(f"{provider}_base_url") or ai_provider_utils.DEFAULT_BASE_URLS[provider],
        "api_mode": cfg.get("openai_api_mode") or "responses",
    }


def deduplicate_records(
    user_id: int,
    incoming: list[dict],
    existing: list[dict],
    progress: Callable[[str], None] | None = None,
    use_ai: bool = True,
) -> tuple[list[dict], dict]:
    """Return records to insert and deterministic/AI deduplication statistics."""
    kept: list[dict] = []
    comparison_pool = list(existing)
    ambiguous: list[tuple[str, dict, list[dict]]] = []
    stats = {"exact_skipped": 0, "ai_skipped": 0, "ai_reviewed": 0, "ai_unavailable": 0}

    for index, candidate in enumerate(incoming):
        same_batch = [
            record for record in comparison_pool
            if _batch(record) == _batch(candidate)
            and company_similarity(_company(record), _company(candidate)) >= COMPANY_SIMILARITY_THRESHOLD
        ]
        if any(_url(record) == _url(candidate) for record in same_batch):
            stats["exact_skipped"] += 1
            continue
        fuzzy_matches = [record for record in same_batch if _job(record) != _job(candidate)]
        if fuzzy_matches:
            ambiguous.append((f"candidate-{index}", candidate, fuzzy_matches[:MAX_SIMILAR_RECORDS]))
            comparison_pool.append(candidate)
        else:
            kept.append(candidate)
            comparison_pool.append(candidate)

    cfg = _ai_config(user_id)
    if ambiguous and cfg and use_ai:
        skill = SKILL_PATH.read_text(encoding="utf-8")
        for offset in range(0, len(ambiguous), AI_BATCH_SIZE):
            batch = ambiguous[offset:offset + AI_BATCH_SIZE]
            if progress:
                progress(f"AI 正在判定模糊重复 {min(offset + len(batch), len(ambiguous))}/{len(ambiguous)}…")
            payload = [
                {
                    "candidate_id": candidate_id,
                    "candidate": _record_payload(candidate),
                    "similar_records": [_record_payload(record) for record in matches],
                }
                for candidate_id, candidate, matches in batch
            ]
            try:
                output = _call_ai_provider(
                    cfg["provider"], cfg["api_key"], cfg["model"], skill,
                    json.dumps(payload, ensure_ascii=False), base_url=cfg["base_url"],
                    api_mode=cfg["api_mode"], max_output_tokens=3000,
                )
                decisions = {str(item.get("candidate_id")): item for item in _json_array(output)}
            except Exception:
                decisions = {}
            for candidate_id, candidate, _matches in batch:
                decision = decisions.get(candidate_id)
                stats["ai_reviewed"] += 1
                if decision and decision.get("duplicate") is True and decision.get("should_add") is False:
                    stats["ai_skipped"] += 1
                    continue
                if not decision:
                    stats["ai_unavailable"] += 1
                kept.append(candidate)
                comparison_pool.append(candidate)
    else:
        if ambiguous and use_ai:
            stats["ai_unavailable"] += len(ambiguous)
        kept.extend(candidate for _candidate_id, candidate, _matches in ambiguous)

    return kept, stats


def find_ai_duplicates(
    user_id: int,
    records: list[dict],
    progress: Callable[[str], None] | None = None,
) -> tuple[list[str], dict]:
    """Return shared-record IDs that AI confirms are covered by an earlier record."""
    cfg = _ai_config(user_id)
    stats = {"ai_reviewed": 0, "ai_duplicates": 0, "ai_unavailable": 0}
    if not cfg:
        stats["ai_unavailable"] = 1
        return [], stats

    survivors: list[dict] = []
    candidates: list[tuple[str, dict, list[dict]]] = []
    # list_shared_records is newest-first; reverse it so established records win.
    for record in reversed(records):
        matches = [
            item for item in survivors
            if _batch(item) == _batch(record)
            and company_similarity(_company(item), _company(record)) >= COMPANY_SIMILARITY_THRESHOLD
        ]
        if matches:
            candidates.append((str(record.get("record_id") or ""), record, matches[:MAX_SIMILAR_RECORDS]))
        survivors.append(record)

    duplicate_ids: list[str] = []
    skill = SKILL_PATH.read_text(encoding="utf-8")
    for offset in range(0, len(candidates), AI_BATCH_SIZE):
        batch = candidates[offset:offset + AI_BATCH_SIZE]
        if progress:
            progress(f"AI 正在复核可能重复的记录 {min(offset + len(batch), len(candidates))}/{len(candidates)}…")
        payload = [
            {"candidate_id": candidate_id, "candidate": _record_payload(record),
             "similar_records": [_record_payload(item) for item in matches]}
            for candidate_id, record, matches in batch
        ]
        try:
            output = _call_ai_provider(
                cfg["provider"], cfg["api_key"], cfg["model"], skill,
                json.dumps(payload, ensure_ascii=False), base_url=cfg["base_url"],
                api_mode=cfg["api_mode"], max_output_tokens=3000,
            )
            decisions = {str(item.get("candidate_id")): item for item in _json_array(output)}
        except Exception:
            decisions = {}
        for candidate_id, _record, _matches in batch:
            stats["ai_reviewed"] += 1
            decision = decisions.get(candidate_id)
            if decision and decision.get("duplicate") is True and decision.get("should_add") is False:
                duplicate_ids.append(candidate_id)
                stats["ai_duplicates"] += 1
            elif not decision:
                stats["ai_unavailable"] += 1
    return duplicate_ids, stats
