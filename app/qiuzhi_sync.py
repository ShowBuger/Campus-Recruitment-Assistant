"""Public campus-job reader for 求职方舟."""
from __future__ import annotations

from datetime import datetime, timedelta

import requests

API_URL = "https://api.qiuzhifangzhou.com/api/campus/getCampusList"


def _deadline_ms(value: str | None) -> int | None:
    if not value:
        return None
    try:
        return int(datetime.strptime(str(value)[:10], "%Y-%m-%d").timestamp() * 1000)
    except ValueError:
        return None


def fetch_shared_fields(days: int = 90) -> tuple[list[dict], int]:
    today = datetime.now().date()
    date_list = [{"date": str(today - timedelta(days=index)), "md5": ""} for index in range(days)]
    response = requests.post(API_URL, json={"dateList": date_list}, timeout=60)
    response.raise_for_status()
    payload = response.json()
    rows = [item for group in payload.get("campusList") or [] for item in group.get("datas") or []]
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
        })
    return fields, len(rows)
