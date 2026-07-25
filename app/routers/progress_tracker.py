"""Generic IMAP recruitment progress tracker."""
import email
import hashlib
import imaplib
import json
import re
import threading
import time
import uuid
from datetime import datetime, timezone
from email.header import decode_header
from email.message import Message
from email.utils import parsedate_to_datetime
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator

from app import ai_provider_utils, auth as auth_module, bus, database, local_records, state

router = APIRouter(prefix="/api/progress-tracker", tags=["progress-tracker"])
EMAIL_CLASSIFIER_SKILL = (
    Path(__file__).resolve().parents[2]
    / "skills" / "recruitment-email-classifier" / "SKILL.md"
)
_syncing_users: set[int] = set()
_sync_lock = threading.Lock()
_scheduler_started = False

STAGE_DEFS: list[dict] = [
    {
        "name": "已挂",
        "positive": ("很遗憾", "未能通过", "未通过", "流程终止", "不予录用",
                      "不再推进", "申请终止", "岗位已关闭"),
        "negative": (),
        "base_confidence": 0.88,
    },
    {
        "name": "OC",
        "positive": ("录用通知", "录取通知", "意向书", "入职邀请", "offer letter"),
        "negative": ("未通过", "不匹配", "不合适"),
        "base_confidence": 0.94,
    },
    {
        "name": "面试",
        "positive": ("面试邀请", "面试通知", "面试安排", "确认面试时间",
                     "面试时间", "确认面试", "面试地点",
                     "一面", "二面", "三面", "终面", "复试通知"),
        "negative": ("面试结果将在之后", "面试未通过", "面试不通过", "面试将在之后"),
        "base_confidence": 0.90,
    },
    {
        "name": "机考",
        "positive": ("笔试邀请", "机考通知", "在线测评邀请", "在线测试邀请",
                     "在线笔试", "笔试通知", "笔试时间", "机考时间",
                     "测评邀请", "AI测评", "在线测评", "测评链接"),
        "negative": ("测评已过期", "测评结果通知", "测评完成"),
        "base_confidence": 0.88,
    },
    {
        "name": "已投递",
        "positive": ("网申成功", "投递成功", "申请成功", "简历已收到",
                     "申请已提交", "简历已投递", "投递确认",
                     "感谢您投递", "感谢投递", "已收到您的投递"),
        "negative": (),
        "base_confidence": 0.88,
    },
]

IGNORE_PATTERNS = (
    "订阅", "退订", "newsletter", "宣讲会", "招聘会", "校园活动",
    "密码重置", "安全提醒",
    "职位推荐", "为您推荐", "你可能感兴趣",
    "调查问卷", "满意度调查", "反馈意见",
    "支付成功", "账单", "电子发票",
    # Recruitment solicitations — not application progress
    "欢迎投递", "推荐投递", "邀请投递", "期待您的投递",
)

DATE_FIELDS = {"已投递": "投递时间", "机考": "机考时间", "面试": "一面", "OC": "结果", "已挂": "结果"}


class TrackerConfig(BaseModel):
    email: str = Field(default="", max_length=254)
    authorization_code: str = Field(default="", max_length=500)
    imap_host: str = Field(default="imap.163.com", max_length=255)
    imap_port: int = Field(default=993, ge=1, le=65535)
    enabled: bool = False
    mode: str = "confirm"
    ai_enabled: bool = False
    tracker_ai_provider: str = ""
    tracker_ai_model: str = Field(default="", max_length=100)
    sync_interval_minutes: int = Field(default=30, ge=5, le=1440)

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        value = value.strip()
        if value and not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", value):
            raise ValueError("邮箱地址格式不正确")
        return value

    @field_validator("imap_host")
    @classmethod
    def validate_host(cls, value: str) -> str:
        value = value.strip().lower()
        if not value or not re.match(r"^[a-z0-9.-]+$", value):
            raise ValueError("IMAP 服务器地址格式不正确")
        return value

    @field_validator("mode")
    @classmethod
    def validate_mode(cls, value: str) -> str:
        if value not in {"confirm", "auto"}:
            raise ValueError("进度更新模式不正确")
        return value

    @field_validator("tracker_ai_provider")
    @classmethod
    def validate_ai_provider(cls, value: str) -> str:
        value = value.strip().lower()
        if value and value not in {"deepseek", "openai", "anthropic", "kimi"}:
            raise ValueError("不支持的跟踪 AI 服务商")
        return value

    @field_validator("tracker_ai_model")
    @classmethod
    def validate_ai_model(cls, value: str) -> str:
        value = value.strip()
        if value and (any(ch.isspace() for ch in value) or "/" in value or "\\" in value):
            raise ValueError("跟踪模型名称格式不正确")
        return value


class EventAction(BaseModel):
    action: str
    interview_round: int | None = None

    @field_validator("action")
    @classmethod
    def validate_action(cls, value: str) -> str:
        if value not in {"confirm", "ignore", "create"}:
            raise ValueError("不支持的操作")
        return value


def _decode(value: str | None) -> str:
    parts = []
    for chunk, charset in decode_header(value or ""):
        if isinstance(chunk, bytes):
            try:
                parts.append(chunk.decode(charset or "utf-8", errors="replace"))
            except LookupError:
                parts.append(chunk.decode("utf-8", errors="replace"))
        else:
            parts.append(chunk)
    return "".join(parts).strip()


def _message_text(message: Message) -> str:
    parts = []
    for part in message.walk():
        if part.get_content_maintype() == "multipart" or part.get_filename():
            continue
        if part.get_content_type() not in {"text/plain", "text/html"}:
            continue
        payload = part.get_payload(decode=True) or b""
        text = payload.decode(part.get_content_charset() or "utf-8", errors="replace")
        if part.get_content_type() == "text/html":
            text = re.sub(r"<[^>]+>", " ", text)
        parts.append(text)
        if sum(map(len, parts)) > 20000:
            break
    return re.sub(r"\s+", " ", " ".join(parts))[:20000]


# ── 本地关键词识别辅助函数 ──────────────────────────

def _extract_evidence(text: str, keyword: str, max_len: int = 100) -> str:
    """Extract a context snippet centered on the first occurrence of keyword."""
    idx = text.lower().find(keyword.lower())
    if idx == -1:
        return keyword[:max_len]
    margin = 20
    start = max(0, idx - margin)
    end = min(len(text), idx + len(keyword) + margin)
    snippet = text[start:end].strip()
    if start > 0:
        snippet = "…" + snippet
    if end < len(text):
        snippet = snippet + "…"
    return snippet[:max_len]


def _build_reason(
    stage_name: str, evidence: str, company: str = "",
    is_conflict: bool = False,
) -> str:
    """Build a human-readable reason from classification signals."""
    parts: list[str] = []
    if is_conflict:
        parts.append("多阶段命中，已选择最高置信度")
    parts.append(f"命中「{evidence}」→ {stage_name}")
    if company:
        parts.append(f"匹配公司：{company}")
    return "；".join(parts)


def _domain_from_sender(sender: str) -> str:
    """Extract a candidate company keyword from sender email domain.

    Returns empty string for common personal email services.
    """
    match = re.search(r"@([^.]+)", sender)
    if not match:
        return ""
    domain = match.group(1).lower()
    common = {
        "163", "126", "qq", "gmail", "outlook", "hotmail",
        "yahoo", "sina", "sohu", "aliyun", "foxmail", "yeah",
        "189", "139", "wo", "live", "icloud", "me",
    }
    return "" if domain in common else domain


def _match_company(text: str, records: list[dict], sender: str = "") -> tuple[int, dict | None, str, str]:
    """Match saved records against email text and sender domain.

    Returns (score, record | None, company_name, job_name).
    """
    domain_key = _domain_from_sender(sender)
    matches: list[tuple[int, dict, str, str]] = []
    for record in records:
        fields = record["fields"]
        saved_company = str(fields.get("公司名称") or "").strip()
        saved_job = str(fields.get("秋招岗位") or "").strip()
        score = 0
        # Text-based company match
        if saved_company and saved_company.lower() in text:
            score += 2
        # Domain-based company match
        if score == 0 and domain_key and saved_company:
            company_lower = saved_company.lower()
            if domain_key in company_lower or company_lower in domain_key:
                score += 1
        # Job match (only when company already matched)
        if score > 0 and saved_job and saved_job.lower() in text:
            score += 1
        if score > 0:
            matches.append((score, record, saved_company, saved_job))
    matches.sort(key=lambda item: item[0], reverse=True)
    return matches[0] if matches else (0, None, "", "")


# ── 本地关键词识别 ──────────────────────────────────


def _recognize(subject: str, body: str, records: list[dict], sender: str = "") -> dict | None:
    """Classify a single email using keyword rules with conflict resolution.

    Multi-phase approach:
      1. Reject obvious non-recruitment emails (IGNORE patterns).
      2. Scan each stage for positive / negative keyword signals.
      3. Resolve conflicts across stages by preferring higher base_confidence.
      4. Map to SKILL.md-aligned decision tiers.
    """
    text = f"{subject} {body}".lower().strip()
    text_len = len(text)

    # ── Phase 1: fast rejection ──────────────────────────
    if any(pattern in text for pattern in IGNORE_PATTERNS):
        return None
    # Very short emails with no strong signal → skip
    if text_len < 8:
        return None

    # ── Phase 2: per-stage positive / negative scan ───────
    candidates: list[dict] = []  # {stage_def, keyword, is_clean}

    for stage in STAGE_DEFS:
        matched_keyword = ""

        # Check positive keywords
        for keyword in stage["positive"]:
            if keyword.lower() in text:
                matched_keyword = keyword
                break

        if not matched_keyword:
            continue

        # Check negative keywords
        has_negative = any(
            neg.lower() in text for neg in stage["negative"]
        )
        if has_negative:
            # Positive matched but negative also present → skip this stage
            # (e.g. "面试未通过" matches "面试" pattern but negated)
            continue

        candidates.append({
            "stage": stage,
            "keyword": matched_keyword,
            "is_clean": True,
        })

    if not candidates:
        return None

    # ── Phase 3: conflict resolution ─────────────────────
    # When multiple stages match, prefer highest base_confidence
    candidates.sort(key=lambda c: c["stage"]["base_confidence"], reverse=True)
    chosen = candidates[0]
    is_conflict = len(candidates) > 1

    stage = chosen["stage"]

    # ── Phase 4: company matching ────────────────────────
    score, record, company, job = _match_company(text, records, sender)

    # ── Phase 5: decision tier (SKILL.md-aligned) ────────
    if is_conflict:
        decision_tier = "REVIEW_LOW"
        confidence = 0.68
    elif score >= 2:
        # Company matched at score >= 3 with no conflict → AUTO
        if score >= 3:
            decision_tier = "AUTO"
            confidence = 0.97
        else:
            decision_tier = "REVIEW_HIGH"
            confidence = 0.88
    else:
        # Keyword hit but no company match
        decision_tier = "REVIEW_LOW"
        confidence = 0.68

    evidence = _extract_evidence(text, chosen["keyword"])
    reason = _build_reason(
        stage["name"], evidence, company or "", is_conflict,
    )

    return {
        "progress": stage["name"],
        "confidence": confidence,
        "decision_tier": decision_tier,
        "reason": reason,
        "evidence": evidence,
        "record_id": record["record_id"] if record else None,
        "company": company,
        "job": job,
    }


def _json_object(text: str) -> dict:
    cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip(), flags=re.I)
    try:
        value = json.loads(cleaned)
    except json.JSONDecodeError:
        match = re.search(r"\{[\s\S]*\}", cleaned)
        if not match:
            raise ValueError("模型没有返回 JSON")
        value = json.loads(match.group(0))
    if not isinstance(value, dict):
        raise ValueError("模型返回格式错误")
    return value


def _match_ai_record(company: str, job: str, records: list[dict]) -> tuple[str | None, str, str]:
    def compact(value: str) -> str:
        return re.sub(r"[^0-9a-z\u4e00-\u9fff]+", "", value.casefold())
    company_key, job_key = compact(company), compact(job)
    candidates = []
    for record in records:
        fields = record["fields"]
        saved_company = str(fields.get("公司名称") or "").strip()
        saved_job = str(fields.get("秋招岗位") or "").strip()
        saved_key = compact(saved_company)
        if company_key and saved_key and (
            company_key in saved_key or saved_key in company_key
        ):
            score = 2 + int(bool(job_key and (
                job_key in compact(saved_job) or compact(saved_job) in job_key
            )))
            candidates.append((score, record["record_id"], saved_company, saved_job))
    if not candidates:
        return None, company.strip(), job.strip()
    candidates.sort(reverse=True)
    return candidates[0][1], candidates[0][2], candidates[0][3]


def _ai_recognize_batch(
    user_id: int, messages: list[dict], records: list[dict]
) -> dict[int, dict | None]:
    """Apply the recruitment-email-classifier SOP to one email batch."""
    cfg = database.get_user_config(user_id)
    tracker_cfg = _config(user_id)
    provider = (
        tracker_cfg.get("tracker_ai_provider")
        or cfg.get("ai_provider")
        or "deepseek"
    )
    api_key = cfg.get(f"{provider}_api_key", "")
    if not api_key:
        raise ValueError("大模型识别已开启，但当前 AI 服务未配置 API Key")
    model_defaults = {
        "deepseek": "deepseek-v4-flash",
        "openai": "gpt-5.4-mini",
        "anthropic": "claude-sonnet-5",
        "kimi": "kimi-k3",
    }
    model = (
        tracker_cfg.get("tracker_ai_model")
        or cfg.get(f"{provider}_model")
        or model_defaults[provider]
    )
    base_url = cfg.get(f"{provider}_base_url", "") or ai_provider_utils.DEFAULT_BASE_URLS[provider]
    api_mode = cfg.get("openai_api_mode", "") or "responses"
    from app.routers.ai import _call_ai_provider
    system_prompt = EMAIL_CLASSIFIER_SKILL.read_text(encoding="utf-8")
    message_payload = [
        {
            "uid": item["uid"],
            "subject": item["subject"][:500],
            "sender": item["sender"][:300],
            "body": item["body"][:3500],
        }
        for item in messages
    ]
    saved_records = [
        {
            "record_id": record["record_id"],
            "company": str(record["fields"].get("公司名称") or "")[:120],
            "job": str(record["fields"].get("秋招岗位") or "")[:200],
        }
        for record in records[:300]
    ]
    payload = {"emails": message_payload, "saved_records": saved_records}
    raw = _call_ai_provider(
        provider, api_key, model, system_prompt,
        json.dumps(payload, ensure_ascii=False),
        base_url=base_url, api_mode=api_mode,
        max_output_tokens=None,
    )
    cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw.strip(), flags=re.I)
    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError:
        match = re.search(r"\[[\s\S]*\]", cleaned)
        if not match:
            raise ValueError("模型没有返回有效的批量 JSON")
        parsed = json.loads(match.group(0))
    if not isinstance(parsed, list):
        raise ValueError("模型批量返回格式错误")
    valid_uids = {item["uid"] for item in messages}
    results: dict[int, dict | None] = {uid: None for uid in valid_uids}
    record_map = {record["record_id"]: record for record in records}
    tier_confidence = {
        "AUTO": 0.97,
        "REVIEW_HIGH": 0.88,
        "REVIEW_LOW": 0.68,
        "IGNORE": 0.20,
    }
    seen_uids: set[int] = set()
    for item in parsed:
        if not isinstance(item, dict):
            continue
        try:
            uid = int(item.get("uid"))
        except (TypeError, ValueError):
            continue
        if uid not in valid_uids:
            continue
        if uid in seen_uids:
            raise ValueError(f"模型重复返回邮件 UID {uid}")
        seen_uids.add(uid)
        progress = str(item.get("progress") or "").strip()
        if not item.get("is_recruitment"):
            continue
        tier = str(item.get("decision_tier") or "").strip().upper()
        if progress not in {"已投递", "机考", "面试", "OC", "已挂"}:
            raise ValueError(f"模型返回了不支持的招聘阶段：{progress or '空'}")
        if tier not in tier_confidence or tier == "IGNORE":
            raise ValueError(f"模型返回了无效的置信度等级：{tier or '空'}")
        company, job = str(item.get("company") or ""), str(item.get("job") or "")
        proposed_id = str(item.get("matched_record_id") or "").strip()
        matched = record_map.get(proposed_id)
        if matched:
            fields = matched["fields"]
            saved_company = str(fields.get("公司名称") or "").strip()
            saved_job = str(fields.get("秋招岗位") or "").strip()
            if company:
                def compact(value: str) -> str:
                    return re.sub(r"[^0-9a-z\u4e00-\u9fff]+", "", value.casefold())
                company_key, saved_key = compact(company), compact(saved_company)
                if not company_key or not saved_key or (
                    company_key not in saved_key and saved_key not in company_key
                ):
                    matched = None
            if matched:
                record_id, company, job = proposed_id, saved_company, saved_job
        if not matched:
            record_id, company, job = _match_ai_record(company, job, records)
        scheduled = item.get("scheduled_ms")
        deadline = item.get("deadline_ms")
        try:
            scheduled_ms = int(scheduled) if scheduled is not None else None
        except (TypeError, ValueError):
            scheduled_ms = None
        try:
            deadline_ms = int(deadline) if deadline is not None else None
        except (TypeError, ValueError):
            deadline_ms = None
        try:
            interview_round = int(item.get("interview_round") or 0) or None
        except (TypeError, ValueError):
            interview_round = None
        results[uid] = {
            "progress": progress,
            "confidence": tier_confidence[tier],
            "decision_tier": tier,
            "record_id": record_id,
            "company": company,
            "job": job,
            "reason": str(item.get("reason") or "")[:200],
            "scheduled_ms": scheduled_ms,
            "deadline_ms": deadline_ms,
            "interview_round": interview_round,
            "time_reason": str(item.get("time_reason") or "")[:120],
        }
    if seen_uids != valid_uids:
        missing = sorted(valid_uids - seen_uids)
        raise ValueError(f"模型遗漏了 {len(missing)} 封邮件的判断结果")
    return results


def _config(user_id: int) -> dict:
    db = database.get_db()
    row = db.execute("SELECT * FROM email_tracker_configs WHERE user_id = ?", (user_id,)).fetchone()
    return dict(row) if row else {}


def _connect(cfg: dict):
    client = imaplib.IMAP4_SSL(cfg["imap_host"], int(cfg["imap_port"]), timeout=20)
    try:
        client.login(cfg["email"], cfg["authorization_code"])
    except imaplib.IMAP4.error as exc:
        raise ValueError("邮箱认证失败，请检查 IMAP 服务和客户端授权码") from exc
    # NetEase/Coremail requires RFC 2971 IMAP ID before selecting a mailbox.
    capabilities = {item.decode().upper() if isinstance(item, bytes) else str(item).upper()
                    for item in client.capabilities}
    if "ID" in capabilities:
        imaplib.Commands.setdefault("ID", ("AUTH",))
        status, data = client._simple_command(
            "ID",
            '("name" "CampusRecruitmentAssistant" "version" "1.0" '
            '"vendor" "CampusRecruitmentAssistant")',
        )
        if status != "OK":
            client.logout()
            raise ValueError("邮箱服务器拒绝客户端身份验证")
    status, data = client.select("INBOX", readonly=True)
    if status != "OK":
        detail = " ".join(
            item.decode(errors="replace") if isinstance(item, bytes) else str(item)
            for item in (data or [])
        )
        client.logout()
        if "Unsafe Login" in detail:
            raise ValueError("邮箱服务器阻止了不安全登录，请确认已开启 IMAP 并使用客户端授权码")
        raise ValueError(f"无法打开收件箱：{detail or '服务器拒绝访问'}")
    return client


def _close_client(client) -> None:
    try:
        client.logout()
    except (imaplib.IMAP4.error, OSError):
        try:
            client.shutdown()
        except (imaplib.IMAP4.error, OSError):
            pass


def _fetch_message_prefix(client, cfg: dict, uid: int) -> tuple[object, Message]:
    """Fetch enough of a message to classify it without downloading attachments."""
    command = "(BODY.PEEK[]<0.30000>)"
    for attempt in range(2):
        try:
            status, raw = client.uid("fetch", str(uid), command)
            payload = next(
                (
                    item[1]
                    for item in (raw or [])
                    if isinstance(item, tuple) and len(item) > 1 and isinstance(item[1], bytes)
                ),
                None,
            )
            if status != "OK" or not payload:
                raise RuntimeError(f"无法读取邮件 UID {uid}")
            return client, email.message_from_bytes(payload)
        except (imaplib.IMAP4.abort, imaplib.IMAP4.error, OSError) as exc:
            _close_client(client)
            if attempt == 0:
                try:
                    client = _connect(cfg)
                    continue
                except (ValueError, imaplib.IMAP4.error, OSError) as reconnect_exc:
                    raise RuntimeError("邮箱连接中断，自动重连失败") from reconnect_exc
            raise RuntimeError(f"读取邮件 UID {uid} 时连接中断") from exc
    raise RuntimeError(f"无法读取邮件 UID {uid}")


def _apply_event(user_id: int, event: dict, interview_round: int | None = None) -> None:
    if not event.get("record_id"):
        raise ValueError("该邮件尚未匹配到个人总表岗位")
    fields = {"进展": [event["progress"]]}
    date_field = DATE_FIELDS.get(event["progress"])
    if date_field:
        # Prefer AI-extracted scheduled time over email received time
        ts = event.get("scheduled_ms") or event.get("received_ms") or int(time.time() * 1000)
        fields[date_field] = ts
        # For 面试, map interview_round to the correct date field
        if event["progress"] == "面试":
            round_field = {1: "一面", 2: "二面", 3: "三面"}.get(
                interview_round or event.get("interview_round")
            )
            if round_field and round_field != date_field:
                fields[round_field] = ts
    if not local_records.update_record(user_id, event["record_id"], fields):
        raise LookupError("对应岗位已不存在")
    state.set_cache(user_id, local_records.get_dashboard_data(user_id))


def sync_user(user_id: int, *, test_only: bool = False, progress_callback=None) -> dict:
    def report(stage: str, progress: int, total: int = 0) -> None:
        if progress_callback:
            progress_callback(stage, progress, total)

    with _sync_lock:
        if user_id in _syncing_users:
            raise RuntimeError("该邮箱正在同步")
        _syncing_users.add(user_id)
    try:
        cfg = _config(user_id)
        if not cfg.get("email") or not cfg.get("authorization_code"):
            raise ValueError("请先填写邮箱和客户端授权码")
        report("连接邮箱", 5)
        client = _connect(cfg)
        report("打开收件箱", 8)
        last_uid = int(cfg.get("last_uid") or 0)
        report("检查新增邮件", 10)
        status, data = client.uid("search", None, "ALL" if test_only else (
            f"UID {last_uid + 1}:*" if last_uid else "ALL"
        ))
        if status != "OK":
            _close_client(client)
            raise RuntimeError("无法读取邮箱列表")
        limit = 10 if test_only else 20
        found_uids = [int(x) for x in (data[0] or b"").split()]
        # Some IMAP servers interpret a reversed `UID n:*` range as including
        # the current maximum UID. Enforce the incremental boundary locally so
        # an empty inbox delta can never trigger a repeated model call.
        if not test_only:
            found_uids = [uid for uid in found_uids if uid > last_uid]
        uids = found_uids[-limit:]
        report("缓存邮件", 12, len(uids))
        db = database.get_db()
        messages: list[dict] = []
        failed_uids: list[int] = []
        for index, uid in enumerate(reversed(uids) if test_only else uids, 1):
            cached = db.execute(
                """SELECT subject, sender, body_excerpt, received_ms
                   FROM email_tracker_cache
                   WHERE user_id = ? AND mailbox = ? AND message_uid = ?""",
                (user_id, cfg["email"].casefold(), uid),
            ).fetchone()
            if cached:
                messages.append({
                    "uid": uid, "subject": cached["subject"], "sender": cached["sender"],
                    "body": cached["body_excerpt"], "received_ms": cached["received_ms"],
                })
            else:
                try:
                    client, message = _fetch_message_prefix(client, cfg, uid)
                except RuntimeError as exc:
                    failed_uids.append(uid)
                    bus.log(f"邮件读取失败 · 用户#{user_id} · {exc}", channel="tracker", level="warn")
                    continue
                try:
                    received = parsedate_to_datetime(message.get("Date")) if message.get("Date") else datetime.now(timezone.utc)
                    received_ms = int(received.timestamp() * 1000)
                except (TypeError, ValueError, OverflowError):
                    received_ms = int(time.time() * 1000)
                subject = _decode(message.get("Subject"))[:500]
                sender = _decode(message.get("From"))[:500]
                body = _message_text(message)[:6000]
                digest = hashlib.sha256(
                    f"{subject}\0{sender}\0{body}".encode("utf-8", errors="replace")
                ).hexdigest()
                with database._write_lock:
                    db.execute(
                        """INSERT OR REPLACE INTO email_tracker_cache
                           (user_id, mailbox, message_uid, subject, sender, body_excerpt,
                            received_ms, content_hash, fetched_at)
                           VALUES (?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))""",
                        (user_id, cfg["email"].casefold(), uid, subject, sender, body,
                         received_ms, digest),
                    )
                    db.commit()
                messages.append({
                    "uid": uid, "subject": subject, "sender": sender,
                    "body": body, "received_ms": received_ms,
                })
            report("缓存邮件", 12 + round(38 * index / max(1, len(uids))), len(uids))
        _close_client(client)
        records = local_records.list_records(user_id)
        report("AI 批量分析" if cfg.get("ai_enabled") else "本地分析", 55, len(messages))
        analysis_error = ""
        ai_fallback = False
        if cfg.get("ai_enabled") and messages:
            try:
                results = _ai_recognize_batch(user_id, messages, records)
            except Exception as exc:
                analysis_error = str(exc)[:300]
                ai_fallback = True
                report("AI 不可用，切换本地识别", 68, len(messages))
                results = {
                    item["uid"]: _recognize(item["subject"], item["body"], records, sender=item.get("sender", ""))
                    for item in messages
                }
                bus.log(
                    f"邮件 AI 不可用，已切换本地识别 · 用户#{user_id} · {analysis_error}",
                    channel="tracker", level="warn",
                )
        else:
            results = {
                item["uid"]: _recognize(item["subject"], item["body"], records, sender=item.get("sender", ""))
                for item in messages
            }
        report("整理识别结果", 82, len(messages))

        if test_only:
            previews = []
            message_map = {item["uid"]: item for item in messages}
            for uid in reversed(uids):
                item = message_map.get(uid)
                if not item:
                    previews.append({
                        "id": 0, "subject": f"邮件 UID {uid}", "sender": "",
                        "company": "", "job": "", "progress": "读取失败", "confidence": 0,
                        "record_id": None, "status": "error", "created_at": "",
                        "error": "邮箱连接中断，稍后可重新测试",
                    })
                    continue
                result = results.get(uid)
                previews.append({
                    "id": 0, "subject": item["subject"], "sender": item["sender"],
                    "received_ms": item["received_ms"],
                    "company": result.get("company", "") if result else "",
                    "job": result.get("job", "") if result else "",
                    "progress": result.get("progress", "") if result else "非招聘邮件",
                    "confidence": result.get("confidence", 0) if result else 0,
                    "decision_tier": result.get("decision_tier", "IGNORE") if result else "IGNORE",
                    "reason": result.get("reason", "") if result else "",
                    "record_id": result.get("record_id") if result else None,
                    "status": "preview", "created_at": "",
                })
            report("完成", 100, len(previews))
            mode_note = "；AI 不可用，已自动切换本地识别" if ai_fallback else ""
            return {
                "success": True,
                "message": f"测试同步完成：已读取并判断 {len(previews)} 封最近邮件{mode_note}",
                "events": previews,
                "count": len(previews),
                "ai_enabled": bool(cfg.get("ai_enabled")),
                "ai_fallback": ai_fallback,
                "analysis_error": analysis_error,
            }
        detected = applied = 0
        for item in messages:
            uid = item["uid"]
            result = results.get(uid)
            if not result:
                continue
            result["received_ms"] = item["received_ms"]
            event_status = "pending"
            if (
                cfg.get("mode") == "auto"
                and result["record_id"]
                and result.get("decision_tier") == "AUTO"
                and result["confidence"] >= .94
            ):
                _apply_event(user_id, result)
                event_status, applied = "applied", applied + 1
            if event_status == "applied":
                detected += 1
                continue
            with database._write_lock:
                db.execute(
                    """INSERT OR IGNORE INTO email_tracker_events
                       (user_id, message_uid, subject, sender, received_ms, company, job,
                       progress, confidence, decision_tier, reason, record_id, status,
                       scheduled_ms, deadline_ms, interview_round, time_reason)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (user_id, uid, item["subject"], item["sender"],
                     item["received_ms"], result["company"], result["job"], result["progress"],
                     result["confidence"], result.get("decision_tier", "REVIEW_LOW"),
                     result.get("reason", "")[:200], result["record_id"], event_status,
                     result.get("scheduled_ms"), result.get("deadline_ms"),
                     result.get("interview_round"), result.get("time_reason", "")[:120]),
                )
                db.commit()
            detected += 1
        max_uid = (min(failed_uids) - 1) if failed_uids else max(uids, default=last_uid)
        with database._write_lock:
            db.execute(
                """UPDATE email_tracker_configs SET last_uid = ?, last_sync_at = datetime('now'),
                   last_error = '' WHERE user_id = ?""", (max_uid, user_id)
            )
            db.execute(
                """DELETE FROM email_tracker_cache
                   WHERE user_id = ? AND fetched_at < datetime('now', '-30 days')""",
                (user_id,),
            )
            db.commit()
        report("完成", 100, len(messages))
        mode_note = "；AI 不可用，已切换本地识别" if ai_fallback else ""
        return {
            "success": True,
            "message": f"同步完成：识别 {detected} 条，自动更新 {applied} 条{mode_note}",
            "detected": detected, "applied": applied, "ai_fallback": ai_fallback,
            "analysis_error": analysis_error,
        }
    finally:
        with _sync_lock:
            _syncing_users.discard(user_id)


def _update_task(task_id: str, *, stage: str, progress: int, total: int = 0) -> None:
    with database._write_lock:
        db = database.get_db()
        db.execute(
            """UPDATE email_tracker_tasks
               SET stage = ?, progress = ?, total = ?, updated_at = datetime('now')
               WHERE id = ?""",
            (stage, progress, total, task_id),
        )
        db.commit()


def _run_task(task_id: str, user_id: int, test_only: bool) -> None:
    with database._write_lock:
        db = database.get_db()
        db.execute(
            """UPDATE email_tracker_tasks SET status = 'running', stage = '连接邮箱',
               progress = 2, updated_at = datetime('now') WHERE id = ?""",
            (task_id,),
        )
        db.commit()
    try:
        result = sync_user(
            user_id, test_only=test_only,
            progress_callback=lambda stage, progress, total=0: _update_task(
                task_id, stage=stage, progress=progress, total=total
            ),
        )
        with database._write_lock:
            db = database.get_db()
            db.execute(
                """UPDATE email_tracker_tasks SET status = 'completed', stage = '完成',
                   progress = 100, result_json = ?, updated_at = datetime('now')
                   WHERE id = ?""",
                (json.dumps(result, ensure_ascii=False), task_id),
            )
            db.commit()
    except Exception as exc:
        with database._write_lock:
            db = database.get_db()
            db.execute(
                """UPDATE email_tracker_tasks SET status = 'failed', stage = '同步失败',
                   error = ?, updated_at = datetime('now') WHERE id = ?""",
                (str(exc)[:500], task_id),
            )
            db.commit()


def _create_task(user_id: int, *, test_only: bool) -> dict:
    running = database.get_db().execute(
        """SELECT id, status, stage, progress, total FROM email_tracker_tasks
           WHERE user_id = ? AND status IN ('queued', 'running')
           ORDER BY created_at DESC LIMIT 1""",
        (user_id,),
    ).fetchone()
    if running:
        return {"success": True, "task": dict(running), "message": "已有同步任务正在执行"}
    task_id = uuid.uuid4().hex
    with database._write_lock:
        db = database.get_db()
        db.execute(
            """INSERT INTO email_tracker_tasks (id, user_id, kind, status, stage, progress)
               VALUES (?, ?, ?, 'queued', '等待开始', 0)""",
            (task_id, user_id, "test" if test_only else "sync"),
        )
        db.commit()
    threading.Thread(
        target=_run_task, args=(task_id, user_id, test_only), daemon=True
    ).start()
    return {
        "success": True,
        "task": {"id": task_id, "status": "queued", "stage": "等待开始", "progress": 0},
        "message": "同步任务已开始",
    }


@router.get("")
def get_tracker(user: dict = Depends(auth_module.get_current_user)):
    cfg = _config(user["user_id"])
    db = database.get_db()
    events = db.execute(
        """SELECT * FROM email_tracker_events WHERE user_id = ? AND status = 'pending'
           ORDER BY id DESC LIMIT 50""", (user["user_id"],)
    ).fetchall()
    return {
        "config": {
            "email": cfg.get("email", ""),
            "imap_host": cfg.get("imap_host", "imap.163.com"),
            "imap_port": cfg.get("imap_port", 993),
            "enabled": bool(cfg.get("enabled")),
            "mode": cfg.get("mode", "confirm"),
            "ai_enabled": bool(cfg.get("ai_enabled")),
            "tracker_ai_provider": cfg.get("tracker_ai_provider", ""),
            "tracker_ai_model": cfg.get("tracker_ai_model", ""),
            "sync_interval_minutes": int(cfg.get("sync_interval_minutes") or 30),
            "authorization_code_saved": bool(cfg.get("authorization_code")),
            "last_sync_at": cfg.get("last_sync_at"),
            "last_error": cfg.get("last_error", ""),
        },
        "events": [dict(row) for row in events],
    }


@router.post("")
def save_tracker(body: TrackerConfig, user: dict = Depends(auth_module.get_current_user)):
    current = _config(user["user_id"])
    code = body.authorization_code.strip() or current.get("authorization_code", "")
    if body.enabled and (not body.email or not code):
        raise HTTPException(status_code=422, detail="启用进度跟踪前请填写邮箱和客户端授权码")
    if body.ai_enabled:
        ai_cfg = database.get_user_config(user["user_id"])
        provider = body.tracker_ai_provider or ai_cfg.get("ai_provider") or "deepseek"
        if not ai_cfg.get(f"{provider}_api_key"):
            raise HTTPException(status_code=422, detail="所选服务商尚未保存 API Key")
        if not body.tracker_ai_model:
            raise HTTPException(status_code=422, detail="请选择自动跟踪使用的 AI 模型")
    with database._write_lock:
        db = database.get_db()
        db.execute(
            """INSERT INTO email_tracker_configs
               (user_id, email, authorization_code, imap_host, imap_port, enabled, mode,
                ai_enabled, tracker_ai_provider, tracker_ai_model, sync_interval_minutes)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(user_id) DO UPDATE SET email=excluded.email,
               authorization_code=excluded.authorization_code, imap_host=excluded.imap_host,
               imap_port=excluded.imap_port, enabled=excluded.enabled, mode=excluded.mode,
               ai_enabled=excluded.ai_enabled,
               tracker_ai_provider=excluded.tracker_ai_provider,
               tracker_ai_model=excluded.tracker_ai_model,
               sync_interval_minutes=excluded.sync_interval_minutes""",
            (user["user_id"], body.email, code, body.imap_host, body.imap_port,
             int(body.enabled), body.mode, int(body.ai_enabled),
             body.tracker_ai_provider, body.tracker_ai_model,
             body.sync_interval_minutes),
        )
        db.commit()
    return {"success": True, "message": "进度跟踪配置已保存"}


@router.get("/ai-models")
def tracker_ai_models(user: dict = Depends(auth_module.get_current_user)):
    user_id = user["user_id"]
    cfg = database.get_user_config(user_id)
    db = database.get_db()
    cached = {
        row["provider"]: row["models_json"]
        for row in db.execute(
            "SELECT provider, models_json FROM ai_model_cache WHERE user_id = ?",
            (user_id,),
        ).fetchall()
    }
    providers = []
    labels = {
        "deepseek": "DeepSeek", "openai": "OpenAI GPT",
        "anthropic": "Claude", "kimi": "Kimi",
    }
    defaults = {
        "deepseek": "deepseek-v4-flash", "openai": "gpt-5.4-mini",
        "anthropic": "claude-sonnet-5", "kimi": "kimi-k3",
    }
    current_provider = cfg.get("ai_provider") or "deepseek"
    provider_order = [
        current_provider,
        *(
            provider for provider in ("deepseek", "openai", "anthropic", "kimi")
            if provider != current_provider
        ),
    ]
    for provider in provider_order:
        if not cfg.get(f"{provider}_api_key"):
            continue
        try:
            models = json.loads(cached.get(provider) or "[]")
        except (json.JSONDecodeError, TypeError):
            models = []
        if not isinstance(models, list):
            models = []
        configured_model = str(
            cfg.get(f"{provider}_model") or defaults[provider]
        ).strip()
        values = []
        for model in [configured_model, *models]:
            model = str(model or "").strip()
            if model and model not in values:
                values.append(model)
        providers.append({
            "provider": provider,
            "label": labels[provider],
            "models": values,
            "catalog_loaded": bool(models),
        })
    return {"providers": providers}


@router.post("/test")
def test_tracker(user: dict = Depends(auth_module.get_current_user)):
    cfg = _config(user["user_id"])
    if not cfg.get("email") or not cfg.get("authorization_code"):
        raise HTTPException(status_code=422, detail="请先填写邮箱和客户端授权码")
    return _create_task(user["user_id"], test_only=True)


@router.post("/sync")
def run_tracker(user: dict = Depends(auth_module.get_current_user)):
    cfg = _config(user["user_id"])
    if not cfg.get("email") or not cfg.get("authorization_code"):
        raise HTTPException(status_code=422, detail="请先填写邮箱和客户端授权码")
    return _create_task(user["user_id"], test_only=False)


@router.get("/tasks/{task_id}")
def get_task(task_id: str, user: dict = Depends(auth_module.get_current_user)):
    row = database.get_db().execute(
        """SELECT id, kind, status, stage, progress, total, result_json, error,
                  created_at, updated_at
           FROM email_tracker_tasks WHERE id = ? AND user_id = ?""",
        (task_id, user["user_id"]),
    ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="同步任务不存在")
    task = dict(row)
    raw_result = task.pop("result_json", "{}")
    try:
        task["result"] = json.loads(raw_result or "{}")
    except json.JSONDecodeError:
        task["result"] = {}
    return {"task": task}


@router.post("/reset")
def reset_tracker(user: dict = Depends(auth_module.get_current_user)):
    user_id = user["user_id"]
    with _sync_lock:
        active_task = database.get_db().execute(
            """SELECT 1 FROM email_tracker_tasks
               WHERE user_id = ? AND status IN ('queued', 'running') LIMIT 1""",
            (user_id,),
        ).fetchone()
        if user_id in _syncing_users or active_task:
            raise HTTPException(status_code=409, detail="同步任务正在运行，请完成后再清空")
        with database._write_lock:
            db = database.get_db()
            try:
                db.execute("BEGIN IMMEDIATE")
                db.execute("DELETE FROM email_tracker_events WHERE user_id = ?", (user_id,))
                db.execute("DELETE FROM email_tracker_cache WHERE user_id = ?", (user_id,))
                db.execute("DELETE FROM email_tracker_tasks WHERE user_id = ?", (user_id,))
                db.execute(
                    """UPDATE email_tracker_configs
                       SET last_uid = 0, last_sync_at = NULL, last_error = ''
                       WHERE user_id = ?""",
                    (user_id,),
                )
                db.commit()
            except Exception:
                db.rollback()
                raise
    return {
        "success": True,
        "message": "同步缓存已清空，下次将按首次同步重新读取",
    }


@router.post("/events/{event_id}")
def act_event(event_id: int, body: EventAction, user: dict = Depends(auth_module.get_current_user)):
    db = database.get_db()
    row = db.execute(
        "SELECT * FROM email_tracker_events WHERE id = ? AND user_id = ?",
        (event_id, user["user_id"]),
    ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="识别结果不存在")
    event = dict(row)
    if event["status"] != "pending":
        raise HTTPException(status_code=409, detail="该识别结果已经处理")
    if body.action == "confirm":
        try:
            _apply_event(user["user_id"], event, body.interview_round)
        except (ValueError, LookupError) as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
    elif body.action == "create":
        if event.get("record_id"):
            raise HTTPException(status_code=409, detail="该更新已经匹配到个人总表岗位")
        fields = {
            "公司名称": event.get("company") or "待补充公司",
            "秋招岗位": event.get("job") or "待补充岗位",
            "城市": "待补充",
            "批次": "秋招",
            "进展": [event["progress"]],
        }
        date_field = DATE_FIELDS.get(event["progress"])
        if date_field:
            fields[date_field] = event.get("received_ms") or int(time.time() * 1000)
        local_records.create_record(user["user_id"], fields)
        state.set_cache(user["user_id"], local_records.get_dashboard_data(user["user_id"]))
    with database._write_lock:
        db.execute("DELETE FROM email_tracker_events WHERE id = ? AND user_id = ?",
                   (event_id, user["user_id"]))
        db.commit()
    messages = {"confirm": "进度已更新", "create": "已新增投递记录", "ignore": "已放弃该更新"}
    return {"success": True, "message": messages[body.action]}


def _scheduler_loop():
    while True:
        time.sleep(60)
        try:
            rows = database.get_db().execute(
                """SELECT user_id FROM email_tracker_configs
                   WHERE enabled = 1
                     AND (last_sync_at IS NULL OR
                          datetime(last_sync_at, '+' || sync_interval_minutes || ' minutes')
                          <= datetime('now'))"""
            ).fetchall()
            for row in rows:
                try:
                    sync_user(row["user_id"])
                except Exception as exc:
                    with database._write_lock:
                        db = database.get_db()
                        db.execute(
                            "UPDATE email_tracker_configs SET last_error = ? WHERE user_id = ?",
                            (str(exc)[:500], row["user_id"]),
                        )
                        db.commit()
                    bus.log(f"邮箱进度跟踪失败 · 用户#{row['user_id']} · {exc}", channel="tracker", level="warn")
        except Exception as exc:
            bus.log(f"进度跟踪调度异常 · {exc}", channel="tracker", level="error")


def start_scheduler():
    global _scheduler_started
    if _scheduler_started:
        return
    _scheduler_started = True
    threading.Thread(target=_scheduler_loop, daemon=True).start()
