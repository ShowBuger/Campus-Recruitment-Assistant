"""Deterministic and AI-assisted deduplication for shared-job synchronization."""
from __future__ import annotations

import json
import html
import re
import unicodedata
from difflib import SequenceMatcher
from pathlib import Path
from typing import Callable
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from app import ai_provider_utils, database
from app.routers.ai import _call_ai_provider

SKILL_PATH = Path(__file__).resolve().parents[1] / "skills" / "shared-job-deduplication" / "SKILL.md"
COMPANY_SIMILARITY_THRESHOLD = 0.55
AI_BATCH_SIZE = 10
MAX_SIMILAR_RECORDS = 8

_TRACKING_QUERY_KEYS = {
    "from", "source", "src", "scene", "share_token", "spm", "track",
    "tracking", "timestamp", "utm_campaign", "utm_content", "utm_medium",
    "utm_source", "utm_term",
}

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


def _batch_parts(record: dict) -> tuple[str, str]:
    """Return an optional graduation year and a semantic recruitment phase.

    A yearless ``秋招`` record is compatible with ``27秋招`` because one source
    omits the target year. Explicitly different years remain a hard boundary.
    """
    raw = unicodedata.normalize(
        "NFKC", str(_value(record, "batch", "批次", "秋招") or "秋招")
    ).strip().casefold()
    compact = re.sub(r"[\s_\-/]+", "", raw)
    year_match = re.search(r"(?<!\d)(20\d{2}|\d{2})\s*届?", compact)
    year = year_match.group(1) if year_match else ""
    if year and len(year) == 2:
        year = "20" + year
    if "提前批" in compact:
        phase = "提前批"
    elif "春招" in compact:
        phase = "春招"
    elif "实习" in compact or "暑期" in compact:
        phase = "实习"
    elif "秋招" in compact or "校招" in compact or "校园招聘" in compact:
        phase = "秋招"
    else:
        phase = re.sub(r"(?:20)?\d{2}届?", "", compact) or "秋招"
    return year, phase


def _batch(record: dict) -> str:
    year, phase = _batch_parts(record)
    return f"{year}:{phase}" if year else phase


def _same_batch(left: dict, right: dict) -> bool:
    left_year, left_phase = _batch_parts(left)
    right_year, right_phase = _batch_parts(right)
    return left_phase == right_phase and (
        not left_year or not right_year or left_year == right_year
    )


def _job(record: dict) -> str:
    return unicodedata.normalize("NFKC", str(_value(record, "job", "秋招岗位") or "")).strip().casefold()


def normalize_job(value: str) -> str:
    text = unicodedata.normalize("NFKC", str(value or "")).casefold()
    return re.sub(r"[\W_]+", "", text, flags=re.UNICODE)


def job_similarity(left: dict, right: dict) -> float:
    a, b = normalize_job(_job(left)), normalize_job(_job(right))
    if not a or not b:
        return 0.0
    if a == b:
        return 1.0
    return SequenceMatcher(None, a, b).ratio()


def _url(record: dict) -> str:
    raw = str(_value(record, "url", "投递链接") or "").strip()
    if not raw:
        return ""
    previous = ""
    while raw != previous:
        previous = raw
        raw = html.unescape(raw)
    # Some feeds contain the malformed entity ``&amp`` without a semicolon.
    raw = re.sub(r"&(?:amp|#0*38);?", "&", raw, flags=re.I)
    try:
        parts = urlsplit(raw)
        scheme = parts.scheme.casefold()
        if scheme in {"http", "https"}:
            scheme = "https"
        host = parts.netloc.casefold()
        if host.startswith("www."):
            host = host[4:]
        path = re.sub(r"/{2,}", "/", parts.path or "/")
        if path != "/":
            path = path.rstrip("/")
        query = [
            (key, value)
            for key, value in parse_qsl(parts.query, keep_blank_values=True)
            if key.casefold() not in _TRACKING_QUERY_KEYS
            and not key.casefold().startswith("utm_")
        ]
        query.sort(key=lambda item: (item[0].casefold(), item[1]))
        fragment = parts.fragment.strip()
        if fragment.casefold() in {"rd", "wechat_redirect"}:
            fragment = ""
        elif fragment:
            fragment = fragment.rstrip("/")
        return urlunsplit((scheme, host, path, urlencode(query, doseq=True), fragment))
    except ValueError:
        return raw


def _url_domain(url: str) -> str:
    """Extract the domain (netloc) from a URL for structural comparison."""
    if not url:
        return ""
    try:
        return urlsplit(url).netloc.casefold()
    except ValueError:
        return ""


def url_similarity(left: str, right: str) -> float:
    """Compare two URLs by domain match + path prefix similarity.

    Returns a float in [0, 1]:
    - 1.0: exact match after normalization
    - 0.70–0.95: same domain with path prefix overlap
    - 0.45: same domain, different top-level paths
    - 0.0: different domains or empty input
    """
    a = _url({"url": left}) if isinstance(left, str) else _url(left)
    b = _url({"url": right}) if isinstance(right, str) else _url(right)
    if not a or not b:
        return 0.0
    if a == b:
        return 1.0
    try:
        pa = urlsplit(a)
        pb = urlsplit(b)
    except ValueError:
        return 0.0
    if pa.netloc.casefold() != pb.netloc.casefold():
        return 0.0
    seg_a = [s.casefold() for s in pa.path.strip("/").split("/") if s]
    seg_b = [s.casefold() for s in pb.path.strip("/").split("/") if s]
    if seg_a == seg_b:
        return 0.95
    if not seg_a or not seg_b:
        return 0.70
    common = 0
    for sa, sb in zip(seg_a, seg_b):
        if sa == sb:
            common += 1
        else:
            break
    if common == 0:
        return 0.45
    return 0.70 + 0.25 * (common / max(len(seg_a), len(seg_b)))


def _company(record: dict) -> str:
    return str(_value(record, "company", "公司名称") or "").strip()


def _candidate_score(candidate: dict, record: dict) -> float:
    company_score = company_similarity(_company(record), _company(candidate))
    url_score = url_similarity(_url(record), _url(candidate))
    job_score = job_similarity(record, candidate)
    exact_url = bool(_url(record) and _url(record) == _url(candidate))
    return (
        (2.0 if exact_url else 0.0)
        + company_score * 0.8
        + url_score * 0.45
        + job_score * 0.35
    )


def _similar_records(candidate: dict, pool: list[dict]) -> list[dict]:
    """Recall records broadly enough that plausible duplicates reach the AI."""
    matches = []
    candidate_url = _url(candidate)
    for record in pool:
        if not _same_batch(record, candidate):
            continue
        company_score = company_similarity(_company(record), _company(candidate))
        record_url = _url(record)
        url_score = url_similarity(record_url, candidate_url)
        if (
            company_score >= COMPANY_SIMILARITY_THRESHOLD
            or (candidate_url and record_url and candidate_url == record_url)
            or (company_score >= 0.35 and url_score >= 0.95)
        ):
            matches.append(record)
    matches.sort(key=lambda record: _candidate_score(candidate, record), reverse=True)
    return matches[:MAX_SIMILAR_RECORDS]


def _deterministic_duplicate(candidate: dict, matches: list[dict]) -> dict | None:
    """Return a strong duplicate match that does not need an AI decision."""
    candidate_url = _url(candidate)
    candidate_job = normalize_job(_job(candidate))
    for record in matches:
        record_url = _url(record)
        if candidate_url and record_url and candidate_url == record_url:
            return record
    for record in matches:
        if (
            company_similarity(_company(record), _company(candidate)) >= 0.92
            and candidate_job
            and candidate_job == normalize_job(_job(record))
        ):
            return record
    return None


def _record_payload(record: dict) -> dict:
    directions = _value(record, "dir", "嵌入式方向", []) or []
    url = str(_value(record, "url", "投递链接") or "")
    return {
        "record_id": str(record.get("record_id") or record.get("id") or ""),
        "company": _company(record),
        "batch": str(_value(record, "batch", "批次", "秋招") or "秋招"),
        "normalized_batch": _batch(record),
        "job": str(_value(record, "job", "秋招岗位") or "")[:600],
        "url": url,
        "normalized_url": _url(record),
        "url_domain": _url_domain(_url(record)),
        "city": str(_value(record, "city", "城市") or "")[:200],
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
        matches = _similar_records(candidate, comparison_pool)
        if _deterministic_duplicate(candidate, matches):
            stats["exact_skipped"] += 1
            continue
        if matches:
            ambiguous.append((f"candidate-{index}", candidate, matches))
        else:
            kept.append(candidate)
        # Recall later records against this candidate exactly once. If AI later
        # marks it as a duplicate, the earlier established match still remains.
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
                    api_mode=cfg["api_mode"], max_output_tokens=4000,
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
    else:
        if ambiguous and use_ai:
            stats["ai_unavailable"] += len(ambiguous)
        kept.extend(candidate for _candidate_id, candidate, _matches in ambiguous)

    return kept, stats


def find_ai_duplicates(
    user_id: int,
    records: list[dict],
    progress: Callable[[str], None] | None = None,
) -> tuple[dict[str, str], dict]:
    """Return duplicate-to-survivor mappings from rules plus AI review."""
    cfg = _ai_config(user_id)
    stats = {
        "rule_duplicates": 0,
        "ai_reviewed": 0,
        "ai_duplicates": 0,
        "ai_unavailable": 0,
    }

    survivors: list[dict] = []
    candidates: list[tuple[str, dict, list[dict]]] = []
    duplicate_map: dict[str, str] = {}
    # list_shared_records is newest-first; reverse it so established records win.
    for record in reversed(records):
        record_id = str(record.get("record_id") or record.get("id") or "")
        if not record_id:
            continue
        matches = _similar_records(record, survivors)
        exact_match = _deterministic_duplicate(record, matches)
        if exact_match:
            survivor_id = str(exact_match.get("record_id") or exact_match.get("id") or "")
            if survivor_id:
                duplicate_map[record_id] = survivor_id
                stats["rule_duplicates"] += 1
                continue
        if matches:
            candidates.append((record_id, record, matches))
        survivors.append(record)

    if not cfg:
        stats["ai_unavailable"] = len(candidates)
        return duplicate_map, stats

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
                api_mode=cfg["api_mode"], max_output_tokens=4000,
            )
            decisions = {str(item.get("candidate_id")): item for item in _json_array(output)}
        except Exception:
            decisions = {}
        for candidate_id, _record, matches in batch:
            stats["ai_reviewed"] += 1
            decision = decisions.get(candidate_id)
            if decision and decision.get("duplicate") is True and decision.get("should_add") is False:
                valid_match_ids = [
                    str(item.get("record_id") or item.get("id") or "")
                    for item in matches
                    if item.get("record_id") or item.get("id")
                ]
                matched_id = str(decision.get("matched_record_id") or "")
                if matched_id not in valid_match_ids:
                    matched_id = valid_match_ids[0] if valid_match_ids else ""
                if matched_id:
                    duplicate_map[candidate_id] = matched_id
                    stats["ai_duplicates"] += 1
            elif not decision:
                stats["ai_unavailable"] += 1

    # Later candidates may have matched an item that was itself removed. Point
    # every duplicate directly at the final survivor before the database merge.
    for duplicate_id in list(duplicate_map):
        survivor_id = duplicate_map[duplicate_id]
        visited = {duplicate_id}
        while survivor_id in duplicate_map and survivor_id not in visited:
            visited.add(survivor_id)
            survivor_id = duplicate_map[survivor_id]
        duplicate_map[duplicate_id] = survivor_id
    return duplicate_map, stats
