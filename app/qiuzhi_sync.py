"""Public campus-job reader for 求职方舟."""
from __future__ import annotations

from datetime import datetime, timedelta

import requests

API_URL = "https://api.qiuzhifangzhou.com/api/campus/getCampusList"
SOURCE_NAME = "qiuzhifangzhou"


def _deadline_ms(value: str | None) -> int | None:
    if not value:
        return None
    try:
        return int(datetime.strptime(str(value)[:10], "%Y-%m-%d").timestamp() * 1000)
    except ValueError:
        return None


def _normalize_batch(raw: str) -> str:
    """Normalize batch value: strip year prefix, map to standard labels."""
    batch = str(raw or "").strip()
    if not batch:
        return "秋招"
    # Strip leading year prefix like "27" or "2027"
    import re as _re
    batch = _re.sub(r"^(27|2027)\s*", "", batch)
    if "提前批" in batch:
        return "提前批"
    if "秋招" in batch:
        return "秋招"
    if "春招" in batch:
        return "春招"
    if "实习" in batch:
        return "实习"
    return batch or "秋招"


def is_2027_autumn_job(fields: dict) -> bool:
    """Keep only 2027 autumn-campus jobs, including early-batch postings."""
    batch = str(fields.get("批次") or "").replace(" ", "").lower()
    return (
        ("27" in batch or "2027" in batch)
        and ("秋招" in batch or "提前批" in batch)
    )


def fetch_shared_fields(days: int = 90, request_days: int = 3) -> tuple[list[dict], int]:
    today = datetime.now().date()
    date_list = [{"date": str(today - timedelta(days=index)), "md5": ""} for index in range(days)]
    rows = []
    # The public endpoint can time out when all 90 days are requested at once.
    # Smaller independent requests keep a slow date range from blocking the whole sync.
    for index in range(0, len(date_list), max(1, request_days)):
        response = requests.post(API_URL, json={"dateList": date_list[index:index + request_days]}, timeout=30)
        response.raise_for_status()
        payload = response.json()
        rows.extend(item for group in payload.get("campusList") or [] for item in group.get("datas") or [])
    fields = []
    for item in rows:
        company = str(item.get("company") or "").strip()
        job = str(item.get("positions") or "").strip()
        url = str(item.get("applyUrl") or item.get("sourceUrl") or "").strip()
        if not company or not job or not url:
            continue
        fields.append({
            "公司名称": company,
            "秋招岗位": job,
            "城市": str(item.get("locations") or "").strip(),
            "批次": str(item.get("batch") or "秋招").strip() or "秋招",
            "嵌入式方向": ["—"],
            "公司/行业类型": " / ".join(item.get("typeTag") or []) or str(item.get("industry") or "未分类"),
            "投递链接": url,
            "投递截止时间": _deadline_ms(item.get("deadline")),
            "__source": SOURCE_NAME,
        })
    return fields, len(rows)
