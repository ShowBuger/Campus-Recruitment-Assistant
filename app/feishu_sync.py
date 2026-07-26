"""Root-only Feishu table reader and fuzzy record synchronizer."""

from __future__ import annotations

import csv
import io
import json
import os
import re
import shutil
import subprocess
import unicodedata
from datetime import datetime, time, timedelta, timezone
from difflib import SequenceMatcher
from pathlib import Path
from urllib.parse import parse_qs, urlparse


CLI_SCRIPT = Path("/usr/lib/node_modules/@larksuite/cli/scripts/run.js")
MAX_RECORDS = 5000
FIELD_ALIASES = {
    "company": ("公司名称", "公司", "企业名称"),
    "job": ("秋招岗位", "岗位名称", "岗位", "招聘岗位", "职位", "职位名称"),
    "batch": ("批次", "招聘类别", "招聘批次", "校招批次"),
    "city": ("城市", "工作城市", "工作地点", "地点"),
    "directions": ("嵌入式方向", "方向", "岗位方向"),
    "company_type": ("公司/行业类型", "公司类型", "行业类型", "行业"),
    "url": ("投递链接", "投递官网", "入口网址", "投递入口", "入口", "招聘链接", "网申链接"),
    "deadline": ("投递截止时间", "截止时间", "截止日期"),
    "priority": ("优先级",),
    "note": ("备注", "公司/岗位主要业务"),
    "job_jd": ("岗位JD", "岗位 JD", "JD"),
}
JOB_SEPARATOR = re.compile(r"[、,，/／|｜;；\n\r]+")
COMPANY_SUFFIXES = (
    "有限责任公司", "股份有限公司", "集团有限公司", "有限公司",
    "股份公司", "集团公司", "公司", "集团", "控股",
)


class FeishuSyncError(RuntimeError):
    pass


def _cli_prefix() -> list[str]:
    executable = shutil.which("lark-cli")
    if executable:
        return [executable]
    node = shutil.which("node")
    if node and CLI_SCRIPT.is_file():
        return [node, str(CLI_SCRIPT)]
    raise FeishuSyncError("服务器未安装可用的飞书 CLI")


def _run_cli(*args: str, timeout: int = 90) -> dict:
    try:
        result = subprocess.run(
            [*_cli_prefix(), *args],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            env={
                **os.environ,
                "LARKSUITE_CLI_NO_UPDATE_NOTIFIER": "1",
                "LARKSUITE_CLI_NO_SKILLS_NOTIFIER": "1",
            },
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise FeishuSyncError("读取飞书表格超时，请稍后重试") from exc
    output = (result.stdout or "").strip()
    error_output = (result.stderr or "").strip()
    if result.returncode:
        message = error_output or output or "飞书 CLI 调用失败"
        raise FeishuSyncError(message[:800])
    parsed = _parse_cli_json(output)
    if isinstance(parsed, dict) and parsed.get("ok") is False:
        error = parsed.get("error") or {}
        raise FeishuSyncError(str(error.get("message") or error.get("hint") or error)[:800])
    return parsed


def _parse_cli_json(output: str) -> dict:
    """Read the CLI JSON even if it is surrounded by non-JSON notices."""
    try:
        parsed = json.loads(output)
    except json.JSONDecodeError as exc:
        decoder = json.JSONDecoder()
        candidates: list[object] = []
        for match in re.finditer(r"[\[{]", output):
            try:
                value, _ = decoder.raw_decode(output[match.start():])
            except json.JSONDecodeError:
                continue
            candidates.append(value)
        if not candidates:
            raise FeishuSyncError("飞书 CLI 返回了无法解析的数据") from exc
        parsed = next(
            (
                value for value in reversed(candidates)
                if isinstance(value, dict) and ("ok" in value or "data" in value)
            ),
            candidates[-1],
        )
    if not isinstance(parsed, dict):
        raise FeishuSyncError("飞书 CLI 返回了无法解析的数据")
    return parsed


def _walk_dicts(value):
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from _walk_dicts(child)
    elif isinstance(value, list):
        for child in value:
            yield from _walk_dicts(child)


def _find_value(payload, *keys: str):
    for item in _walk_dicts(payload):
        for key in keys:
            if item.get(key) not in (None, ""):
                return item[key]
    return None


def _validate_url(value: str) -> str:
    url = value.strip()
    parsed = urlparse(url)
    hostname = (parsed.hostname or "").lower()
    valid_host = any(
        hostname == domain or hostname.endswith("." + domain)
        for domain in ("feishu.cn", "larksuite.com")
    )
    if parsed.scheme != "https" or not valid_host:
        raise FeishuSyncError("请输入有效的飞书多维表格或电子表格 HTTPS 链接")
    if not any(segment in parsed.path for segment in ("/base/", "/wiki/", "/sheets/")):
        raise FeishuSyncError("链接必须指向飞书多维表格、知识库表格或电子表格")
    return url


def _read_base(url: str) -> list[dict]:
    resolved = _run_cli("base", "+url-resolve", "--url", url, "--as", "user", "--json")
    base_token = _find_value(resolved, "base_token", "app_token")
    table_id = _find_value(resolved, "table_id")
    view_id = _find_value(resolved, "view_id")
    if not base_token or not table_id:
        raise FeishuSyncError("无法从链接解析多维表格 Token 或数据表 ID")
    records: list[dict] = []
    offset = 0
    while len(records) < MAX_RECORDS:
        args = [
            "base", "+record-list", "--base-token", str(base_token),
            "--table-id", str(table_id), "--offset", str(offset),
            "--limit", "200", "--as", "user", "--json",
        ]
        if view_id:
            args.extend(("--view-id", str(view_id)))
        page = _run_cli(*args)
        page_records = []
        for item in _walk_dicts(page):
            candidate = item.get("records") or item.get("items")
            if isinstance(candidate, list) and (
                not candidate or isinstance(candidate[0], dict)
            ):
                page_records = candidate
                break
        fields = [item.get("fields", item) for item in page_records if isinstance(item, dict)]
        records.extend(item for item in fields if isinstance(item, dict))
        if len(page_records) < 200 or not page_records:
            break
        offset += len(page_records)
    return records[:MAX_RECORDS]


def _sheet_rows(payload: dict) -> list[dict]:
    output: list[dict] = []
    sheets = _find_value(payload, "sheets")
    if not isinstance(sheets, list):
        sheets = [payload]
    for sheet in sheets:
        if not isinstance(sheet, dict):
            continue
        rows = sheet.get("rows") or sheet.get("data") or []
        columns = sheet.get("columns") or []
        names = [
            str(column.get("name") or column.get("title") or column.get("id") or "")
            if isinstance(column, dict) else str(column)
            for column in columns
        ]
        sheet_name = str(sheet.get("name") or sheet.get("sheet_name") or "")
        if isinstance(rows, list) and rows and isinstance(rows[0], list):
            matrix = [names, *rows] if names else list(rows)
            header_index = None
            company_headers = {_compact(item) for item in FIELD_ALIASES["company"]}
            job_headers = {_compact(item) for item in FIELD_ALIASES["job"]}
            for index, raw_row in enumerate(matrix[:30]):
                normalized = {_compact(_plain(cell)) for cell in raw_row}
                if normalized & company_headers and normalized & job_headers:
                    header_index = index
                    break
            if header_index is not None:
                names = [_plain(cell) or f"col{index + 1}" for index, cell in enumerate(matrix[header_index])]
                rows = matrix[header_index + 1:]
        for row in rows if isinstance(rows, list) else []:
            if isinstance(row, dict):
                values = row.get("values")
                if isinstance(values, list) and names:
                    mapped = dict(zip(names, values))
                else:
                    mapped = dict(row)
            elif isinstance(row, list) and names:
                mapped = dict(zip(names, row))
            else:
                continue
            mapped["_sheet_name"] = sheet_name
            output.append(mapped)
    return output[:MAX_RECORDS]


def _column_name(number: int) -> str:
    result = ""
    while number > 0:
        number, remainder = divmod(number - 1, 26)
        result = chr(65 + remainder) + result
    return result or "A"


def _csv_rows(payload: dict, sheet_name: str) -> list[dict]:
    annotated = _find_value(payload, "annotated_csv")
    if not isinstance(annotated, str):
        raise FeishuSyncError("飞书电子表格未返回可解析的 CSV 数据")
    clean = re.sub(r"^\[row=\d+\] ", "", annotated, flags=re.MULTILINE)
    matrix = list(csv.reader(io.StringIO(clean)))
    company_headers = {_compact(item) for item in FIELD_ALIASES["company"]}
    job_headers = {_compact(item) for item in FIELD_ALIASES["job"]}
    header_index = None
    for index, raw_row in enumerate(matrix[:30]):
        normalized = {_compact(_plain(cell)) for cell in raw_row}
        if normalized & company_headers and normalized & job_headers:
            header_index = index
            break
    if header_index is None:
        raise FeishuSyncError("前 30 行中未找到“公司名称”和“岗位名称”表头")
    names = [
        _plain(cell) or f"col{index + 1}"
        for index, cell in enumerate(matrix[header_index])
    ]
    output = []
    for raw_row in matrix[header_index + 1:]:
        if not any(_plain(cell) for cell in raw_row):
            continue
        padded = [*raw_row, *([""] * max(0, len(names) - len(raw_row)))]
        mapped = dict(zip(names, padded))
        mapped["_sheet_name"] = sheet_name
        output.append(mapped)
    return output[:MAX_RECORDS]


def _read_sheets(url: str) -> list[dict]:
    query = parse_qs(urlparse(url).query)
    sheet_id = (query.get("sheet") or query.get("sheet_id") or [""])[0]
    workbook = _run_cli("sheets", "+workbook-info", "--url", url, "--as", "user", "--json")
    sheets = _find_value(workbook, "sheets")
    visible = [
        item for item in sheets if isinstance(item, dict) and not item.get("is_hidden")
    ] if isinstance(sheets, list) else []
    if not visible:
        raise FeishuSyncError("电子表格中没有可读取的工作表")
    selected = next(
        (
            item for item in visible
            if sheet_id and str(item.get("sheet_id") or item.get("sheet_name") or "") == sheet_id
        ),
        visible[0] if not sheet_id else None,
    )
    if not selected:
        raise FeishuSyncError("链接指定的工作表不存在或不可见")
    selected_id = str(selected.get("sheet_id") or "")
    sheet_name = str(selected.get("sheet_name") or selected.get("name") or "")
    row_count = min(max(int(selected.get("row_count") or 1), 1), MAX_RECORDS + 30)
    column_count = min(max(int(selected.get("column_count") or 1), 1), 200)
    cell_range = f"A1:{_column_name(column_count)}{row_count}"
    payload = _run_cli(
        "sheets", "+csv-get", "--url", url, "--sheet-id", selected_id,
        "--range", cell_range, "--max-chars", "500000", "--as", "user", "--json",
        timeout=120,
    )
    return _csv_rows(payload, sheet_name)


def read_table(url: str) -> list[dict]:
    validated = _validate_url(url)
    return _read_sheets(validated) if "/sheets/" in urlparse(validated).path else _read_base(validated)


def _plain(value) -> str:
    if value is None:
        return ""
    if isinstance(value, dict):
        for key in ("link", "text", "name", "value"):
            if value.get(key) not in (None, ""):
                return _plain(value[key])
        return ""
    if isinstance(value, list):
        return "、".join(filter(None, (_plain(item) for item in value)))
    return str(value).strip()


def _list_value(value) -> list[str]:
    if isinstance(value, list):
        items = [_plain(item) for item in value]
    else:
        items = JOB_SEPARATOR.split(_plain(value))
    return list(dict.fromkeys(item.strip() for item in items if item.strip()))


def _field(row: dict, key: str):
    normalized = {_compact(str(name)): value for name, value in row.items()}
    for alias in FIELD_ALIASES[key]:
        alias_key = _compact(alias)
        for name, value in normalized.items():
            if (name == alias_key or name.startswith(alias_key)) and value not in (None, "", []):
                return value
    return None


def _batch(value) -> str:
    text = _plain(value)
    if "提前" in text:
        return "提前批"
    if "秋" in text:
        return "秋招"
    return text or "秋招"


def _date_ms(value):
    if value in (None, "", 0):
        return None
    if isinstance(value, (int, float)):
        number = int(value)
        return number * 1000 if number < 10_000_000_000 else number
    match = re.search(r"(20\d{2})[-/.年](\d{1,2})[-/.月](\d{1,2})", _plain(value))
    if not match:
        return None
    parsed = datetime(int(match[1]), int(match[2]), int(match[3]))
    china_tz = timezone(timedelta(hours=8))
    return int(datetime.combine(parsed.date(), time.min, china_tz).timestamp() * 1000)


def map_row(row: dict) -> dict | None:
    company = _plain(_field(row, "company"))
    job = _plain(_field(row, "job"))
    if not company or not job:
        return None
    priority = _plain(_field(row, "priority"))
    if priority not in ("⭐⭐⭐⭐⭐", "⭐⭐⭐⭐", "⭐⭐⭐", "⭐⭐", "⭐"):
        priority = "⭐⭐⭐"
    return {
        "公司名称": company,
        "秋招岗位": job,
        "城市": _plain(_field(row, "city")),
        "批次": _batch(_field(row, "batch") or row.get("_sheet_name")),
        "嵌入式方向": _list_value(_field(row, "directions")),
        "公司/行业类型": _plain(_field(row, "company_type")),
        "投递链接": _plain(_field(row, "url")),
        "投递截止时间": _date_ms(_field(row, "deadline")),
        "进展": ["未投递"],
        "优先级": priority,
        "备注": _plain(_field(row, "note")),
        "岗位JD": _plain(_field(row, "job_jd")),
    }


def _compact(value: str) -> str:
    text = unicodedata.normalize("NFKC", value or "").casefold()
    return re.sub(r"[^0-9a-z\u4e00-\u9fff]+", "", text)


def _company_key(value: str) -> str:
    key = _compact(value)
    changed = True
    while changed:
        changed = False
        for suffix in COMPANY_SUFFIXES:
            suffix_key = _compact(suffix)
            if key.endswith(suffix_key) and len(key) > len(suffix_key):
                key = key[:-len(suffix_key)]
                changed = True
                break
    return key


def _similarity(left: str, right: str, *, company: bool = False) -> float:
    a = _company_key(left) if company else _compact(left)
    b = _company_key(right) if company else _compact(right)
    if not a or not b:
        return 1.0 if a == b else 0.0
    if a == b:
        return 1.0
    shorter, longer = sorted((a, b), key=len)
    containment = 0.0
    minimum = 2 if company else 3
    if len(shorter) >= minimum and shorter in longer:
        containment = 0.94 if company else 0.92
    return max(containment, SequenceMatcher(None, a, b).ratio())


def _job_similarity(left: str, right: str) -> float:
    left_parts = [item for item in JOB_SEPARATOR.split(left or "") if _compact(item)] or [left or ""]
    right_parts = [item for item in JOB_SEPARATOR.split(right or "") if _compact(item)] or [right or ""]
    return max(_similarity(a, b) for a in left_parts for b in right_parts)


def _is_applied(fields: dict) -> bool:
    progress = fields.get("进展") or []
    if not isinstance(progress, list):
        progress = [progress]
    if any(str(item).strip() not in ("", "未投递") for item in progress):
        return True
    return any(
        fields.get(name)
        for name in ("投递时间", "机考时间", "一面", "二面", "三面", "保温", "结果")
    )


def duplicate_match(candidate: dict, existing: list[dict]) -> dict | None:
    candidate_batch = _batch(candidate.get("批次"))
    for record in existing:
        fields = record.get("fields", record)
        if _batch(fields.get("批次")) != candidate_batch:
            continue
        company_score = _similarity(
            candidate.get("公司名称", ""), fields.get("公司名称", ""), company=True
        )
        job_score = _job_similarity(
            candidate.get("秋招岗位", ""), fields.get("秋招岗位", "")
        )
        if company_score >= 0.86 and _is_applied(fields):
            return {
                "record": record,
                "company_score": round(company_score, 3),
                "job_score": round(job_score, 3),
                "reason": "applied_same_batch",
            }
        if company_score >= 0.86 and job_score >= 0.76:
            return {
                "record": record,
                "company_score": round(company_score, 3),
                "job_score": round(job_score, 3),
                "reason": "similar_record",
            }
    return None


def prepare_sync(rows: list[dict], existing: list[dict]) -> tuple[list[dict], list[dict], int]:
    additions: list[dict] = []
    skipped: list[dict] = []
    invalid = 0
    comparison = list(existing)
    for row in rows:
        candidate = map_row(row)
        if not candidate:
            invalid += 1
            continue
        match = duplicate_match(candidate, comparison)
        if match:
            fields = match["record"].get("fields", match["record"])
            skipped.append({
                "company": candidate["公司名称"],
                "job": candidate["秋招岗位"],
                "batch": candidate["批次"],
                "matched_company": fields.get("公司名称", ""),
                "matched_job": fields.get("秋招岗位", ""),
                "company_similarity": match["company_score"],
                "job_similarity": match["job_score"],
                "reason": match["reason"],
            })
            continue
        additions.append(candidate)
        comparison.append({"fields": candidate})
    return additions, skipped, invalid
