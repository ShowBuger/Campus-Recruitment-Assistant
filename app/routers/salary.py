"""Administrator-only salary lookup sourced from a Feishu spreadsheet."""

from __future__ import annotations

import csv
import hashlib
import io
import os
import re
import threading
import time
import unicodedata
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field, field_validator

from app import auth as auth_module, database, feishu_sync
from tools.offershow_scraper import OfferShowError, OfferShowScraper


router = APIRouter(prefix="/api/salaries", tags=["salary"])
SOURCE_URL = os.getenv(
    "SALARY_SOURCE_URL",
    "https://kcn2brthfhqd.feishu.cn/wiki/VyUrwEUqginb3MkhpTxcStKXnmB?from=from_copylink&sheet=sk7E0F",
)
CACHE_SECONDS = 30 * 60
_cache_lock = threading.Lock()
_cache: dict = {"loaded_at": 0.0, "records": [], "sheet_name": ""}
_offershow_cache: dict[str, dict] = {}
OFFERSHOW_CACHE_SECONDS = 10 * 60
ENV_PATH = os.path.join(os.path.dirname(__file__), "..", "..", ".env")
OFFERSHOW_TOKEN_PATH = os.path.join(os.path.dirname(__file__), "..", "..", ".offershow-token")


class OfferShowTokenConfig(BaseModel):
    token: str = Field(default="", max_length=4096)

    @field_validator("token")
    @classmethod
    def validate_token(cls, value: str) -> str:
        value = value.strip()
        if not value:
            return ""
        if value.count(".") != 2 or any(char.isspace() for char in value):
            raise ValueError("Token 格式不正确")
        return value


def require_admin(user: dict = Depends(auth_module.get_current_user)) -> dict:
    if not (user.get("is_root") or user.get("is_admin")):
        raise HTTPException(status_code=403, detail="仅管理员可以查询薪资数据")
    return user


def _compact(value: str) -> str:
    text = unicodedata.normalize("NFKC", value or "").casefold()
    return re.sub(r"[^0-9a-z\u4e00-\u9fff]+", "", text)


def _mask_contact(value: str) -> str:
    text = str(value or "").strip()
    text = re.sub(r"(?<!\d)1\d{10}(?!\d)", "[联系方式已隐藏]", text)
    return re.sub(r"(?i)(vx|v信|微信)\s*[:：]?\s*[a-z0-9_-]{5,}", "微信：[已隐藏]", text)


def _read_salary_sheet() -> tuple[list[dict], str]:
    url = feishu_sync.validate_url(SOURCE_URL)
    query = parse_qs(urlparse(url).query)
    requested_sheet = (query.get("sheet") or query.get("sheet_id") or [""])[0]
    workbook = feishu_sync._run_cli(
        "sheets", "+workbook-info", "--url", url, "--as", "user", "--json"
    )
    sheets = feishu_sync._find_value(workbook, "sheets")
    visible = [item for item in sheets or [] if isinstance(item, dict) and not item.get("is_hidden")]
    selected = next(
        (item for item in visible if str(item.get("sheet_id") or "") == requested_sheet),
        visible[0] if visible and not requested_sheet else None,
    )
    if not selected:
        raise feishu_sync.FeishuSyncError("薪资工作表不存在或不可见")
    sheet_id = str(selected.get("sheet_id") or "")
    sheet_name = str(selected.get("sheet_name") or selected.get("name") or "薪资表")
    row_count = min(max(int(selected.get("row_count") or 1), 1), feishu_sync.MAX_RECORDS)
    column_count = min(max(int(selected.get("column_count") or 1), 1), 100)
    payload = feishu_sync._run_cli(
        "sheets", "+csv-get", "--url", url, "--sheet-id", sheet_id,
        "--range", f"A1:{feishu_sync._column_name(column_count)}{row_count}",
        "--max-chars", "1000000", "--as", "user", "--json", timeout=120,
    )
    annotated = feishu_sync._find_value(payload, "annotated_csv")
    if not isinstance(annotated, str):
        raise feishu_sync.FeishuSyncError("飞书薪资表未返回可解析的数据")
    clean = re.sub(r"^\[row=\d+\] ", "", annotated, flags=re.MULTILINE)
    matrix = list(csv.reader(io.StringIO(clean)))
    header_index = next(
        (
            index for index, row in enumerate(matrix[:30])
            if "公司名称" in {_compact(cell) for cell in row}
            and "offer薪资" in {_compact(cell) for cell in row}
        ),
        None,
    )
    if header_index is None:
        raise feishu_sync.FeishuSyncError("薪资表中未找到公司名称和 Offer 薪资表头")
    headers = [_compact(cell) for cell in matrix[header_index]]
    aliases = {
        "company": ("公司名称", "公司"),
        "salary": ("offer薪资", "薪资", "总包"),
        "city": ("城市", "工作地点"),
        "education": ("个人学历", "学历"),
        "job": ("岗位名称公司信息", "岗位名称", "岗位"),
        "note": ("备注大家可在此处交流", "备注"),
    }
    indexes = {}
    for field, names in aliases.items():
        normalized_names = {_compact(name) for name in names}
        indexes[field] = next((i for i, name in enumerate(headers) if name in normalized_names), None)
    # The source sheet intentionally leaves the city header blank, while its
    # first six data columns keep a stable company/salary/city/education/job/note order.
    fallback_indexes = {"company": 0, "salary": 1, "city": 2, "education": 3, "job": 4, "note": 5}
    for field, fallback in fallback_indexes.items():
        if indexes[field] is None:
            indexes[field] = fallback

    records = []
    for source_row in matrix[header_index + 1:]:
        def cell(field: str) -> str:
            index = indexes.get(field)
            return str(source_row[index]).strip() if index is not None and index < len(source_row) else ""

        company = cell("company")
        salary = cell("salary")
        if not company or not salary or company in {"公司名称", "公司"}:
            continue
        if "微信公众号" in company or "嵌入式校招菌" in company:
            continue
        records.append({
            "id": len(records) + 1,
            "company": company,
            "salary": salary,
            "city": cell("city"),
            "education": cell("education"),
            "job": cell("job"),
            "note": _mask_contact(cell("note")),
        })
    return records, sheet_name


def _salary_records(force: bool = False) -> tuple[list[dict], str, int]:
    with _cache_lock:
        if force or not _cache["records"] or time.time() - _cache["loaded_at"] >= CACHE_SECONDS:
            records, sheet_name = _read_salary_sheet()
            _cache.update(loaded_at=time.time(), records=records, sheet_name=sheet_name)
        return list(_cache["records"]), str(_cache["sheet_name"]), int(_cache["loaded_at"] * 1000)


def _search(records: list[dict], keyword: str, company: str, city: str, education: str, job: str) -> list[dict]:
    filters = {
        "company": company.strip().casefold(), "city": city.strip().casefold(),
        "education": education.strip().casefold(), "job": job.strip().casefold(),
    }
    keyword = keyword.strip().casefold()
    output = []
    for record in records:
        if any(value and value not in str(record[field]).casefold() for field, value in filters.items()):
            continue
        if keyword and keyword not in " ".join(str(record[field]) for field in ("company", "salary", "city", "education", "job")).casefold():
            continue
        output.append(record)
    return output


def _format_offer_salary(position: dict) -> str:
    labels = (("普通", "normal"), ("SP", "sp"), ("SSP", "ssp"))
    values = [f"{label}：{position.get(field)}" for label, field in labels if position.get(field)]
    return " / ".join(values) or "暂未披露"


def _offershow_publish_year(row: dict) -> str:
    for field in ("publish_time", "time"):
        match = re.search(r"(?:19|20)\d{2}", str(row.get(field) or ""))
        if match:
            return match.group(0)
    return ""


def _matches_offershow_filters(record: dict, company: str, job: str, city: str) -> bool:
    filters = {"company": company.casefold(), "job": job.casefold(), "city": city.casefold()}
    return all(
        not value or value in str(record.get(field) or "").casefold()
        for field, value in filters.items()
    )


def _read_offershow_token() -> str:
    token = ""
    if os.path.isfile(OFFERSHOW_TOKEN_PATH):
        with open(OFFERSHOW_TOKEN_PATH, encoding="utf-8") as handle:
            token = handle.read().strip()
    if not token:
        token = os.getenv("OFFERSHOW_ACCESS_TOKEN", "").strip()
    if not token and os.path.isfile(ENV_PATH):
        with open(ENV_PATH, encoding="utf-8") as handle:
            token = next(
                (line.split("=", 1)[1].strip() for line in handle if line.startswith("OFFERSHOW_ACCESS_TOKEN=")),
                "",
            )
    return token


def _effective_offershow_token(user_id: int) -> tuple[str, bool]:
    personal = str(database.get_user_config(user_id).get("offershow_access_token") or "").strip()
    return (personal, True) if personal else (_read_offershow_token(), False)


def _mask_token(token: str) -> str:
    return f"{token[:8]}…{token[-6:]}" if len(token) > 16 else "***"


def _write_offershow_token(token: str) -> None:
    target = Path(OFFERSHOW_TOKEN_PATH).resolve()
    temporary = target.with_name(f".{target.name}.{os.getpid()}.tmp")
    try:
        temporary.write_text(token + "\n", encoding="utf-8")
        os.chmod(temporary, 0o600)
        os.replace(temporary, target)
    finally:
        if temporary.exists():
            temporary.unlink()


def _fetch_offershow_records(keyword: str, token: str | None = None) -> list[dict]:
    """Fetch OfferShow user-submitted salary disclosures for one query."""
    token = (token or _read_offershow_token()).strip()
    if not token:
        raise OfferShowError("未配置 OFFERSHOW_ACCESS_TOKEN")
    with OfferShowScraper(interval=1.0, timeout=20.0) as scraper:
        rows = scraper.search_salary_disclosures(token=token, keyword=keyword)
    return [{
        "id": f"offershow:{row.get('id') or index}",
        "company": str(row.get("company") or "-").strip(),
        "salary": str(row.get("salary") or "暂未披露").strip(),
        "city": str(row.get("city") or row.get("region") or "").strip(),
        "education": str(row.get("xueli") or "").strip(),
        "job": str(row.get("position") or "-").strip(),
        "year": _offershow_publish_year(row),
        "publish_time": str(row.get("publish_time") or "").strip(),
        "source": "offershow",
    } for index, row in enumerate(rows)]


def _cached_offershow_records(keyword: str, token: str) -> list[dict]:
    key = f"{hashlib.sha256(token.encode()).hexdigest()[:16]}:{_compact(keyword)}"
    now = time.time()
    with _cache_lock:
        cached = _offershow_cache.get(key)
        if cached and now - cached["loaded_at"] < OFFERSHOW_CACHE_SECONDS:
            return list(cached["records"])
    records = _fetch_offershow_records(keyword, token)
    with _cache_lock:
        _offershow_cache[key] = {"loaded_at": now, "records": records}
    return list(records)


@router.get("/offershow/config")
def get_offershow_config(user: dict = Depends(auth_module.get_current_user)):
    token, using_personal = _effective_offershow_token(user["user_id"])
    return {
        "success": True, "configured": bool(token),
        "masked_token": _mask_token(token) if token else "",
        "using_personal": using_personal,
        "public_configured": bool(_read_offershow_token()),
    }


@router.post("/offershow/config")
def save_offershow_config(
    payload: OfferShowTokenConfig,
    user: dict = Depends(auth_module.get_current_user),
):
    database.save_offershow_token(user["user_id"], payload.token)
    with _cache_lock:
        _offershow_cache.clear()
    effective = payload.token or _read_offershow_token()
    return {
        "success": True,
        "message": "个人 OfferShow Token 已保存" if payload.token else "已恢复使用公共 Token",
        "configured": bool(effective),
        "using_personal": bool(payload.token),
        "masked_token": _mask_token(effective) if effective else "",
    }


@router.get("")
def list_salaries(
    keyword: str = Query(default="", max_length=100),
    company: str = Query(default="", max_length=100),
    city: str = Query(default="", max_length=100),
    education: str = Query(default="", max_length=100),
    job: str = Query(default="", max_length=100),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=10, le=200),
    _: dict = Depends(auth_module.get_current_user),
):
    try:
        records, sheet_name, updated_at = _salary_records()
    except feishu_sync.FeishuSyncError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    filtered = _search(records, keyword, company, city, education, job)
    start = (page - 1) * page_size
    visible_items = [
        {**{key: value for key, value in record.items() if key != "note"}, "source": "sheet", "year": "2025"}
        for record in filtered[start:start + page_size]
    ]
    return {
        "success": True, "items": visible_items,
        "total": len(filtered), "source_total": len(records), "page": page,
        "page_size": page_size, "sheet_name": sheet_name, "updated_at": updated_at,
    }


@router.get("/offershow")
def search_offershow_salaries(
    keyword: str = Query(default="", max_length=50),
    company: str = Query(default="", max_length=50),
    job: str = Query(default="", max_length=50),
    city: str = Query(default="", max_length=50),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=10, le=200),
    user: dict = Depends(auth_module.get_current_user),
):
    company, job, city = company.strip(), job.strip(), city.strip()
    keyword = keyword.strip() or company or job or city
    if not keyword:
        raise HTTPException(status_code=422, detail="请至少输入公司、岗位或城市中的一项")
    try:
        sheet_records, sheet_name, _ = _salary_records()
    except feishu_sync.FeishuSyncError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    local_records = [
        {**{key: value for key, value in record.items() if key != "note"}, "source": "sheet", "year": "2025"}
        for record in _search(sheet_records, "", company, city, "", job)
    ]
    warning = ""
    try:
        token, _ = _effective_offershow_token(user["user_id"])
        if not token:
            raise OfferShowError("公共 Token 和个人 Token 均未配置")
        remote_records = _cached_offershow_records(keyword, token)
        remote_records = [
            record for record in remote_records
            if _matches_offershow_filters(record, company, job, city)
        ]
    except OfferShowError as exc:
        remote_records = []
        warning = f"OfferShow 暂时不可用，当前仅显示总表结果：{exc}"

    records = []
    seen = set()
    for record in [*local_records, *remote_records]:
        identity = tuple(_compact(str(record.get(field) or "")) for field in ("company", "salary", "job", "city", "education"))
        if identity in seen:
            continue
        seen.add(identity)
        records.append(record)
    start = (page - 1) * page_size
    return {
        "success": True,
        "items": records[start:start + page_size],
        "total": len(records),
        "source_total": len(records),
        "page": page,
        "page_size": page_size,
        "sheet_name": f"{sheet_name} + OfferShow",
        "source": "combined",
        "local_total": len(local_records),
        "offershow_total": len(remote_records),
        "warning": warning,
        "attribution": "总表与 OfferShow 薪资爆料联合查询；OfferShow 数据仅供个人查询与企业内部使用",
    }


@router.post("/refresh")
def refresh_salaries(_: dict = Depends(require_admin)):
    try:
        records, sheet_name, updated_at = _salary_records(force=True)
    except feishu_sync.FeishuSyncError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return {
        "success": True, "message": f"已同步 {len(records)} 条薪资记录",
        "total": len(records), "sheet_name": sheet_name, "updated_at": updated_at,
    }
