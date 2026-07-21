"""看板数据接口：per-user SQLite 职位记录与本地日程。"""
import re
import time as _time_module
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from io import BytesIO
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from typing import Literal

import requests
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field, HttpUrl

from app import auth as auth_module, bus, database, feishu_sync, local_records, record_excel, state

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


# ── 事件类型映射 ────────────────────────────────────────
EVENT_TYPE_FIELD_MAP = {
    "apply": "投递时间",
    "exam": "机考时间",
    "interview1": "一面",
    "interview2": "二面",
    "interview3": "三面",
    "warm": "保温",
    "result": "结果",
    "deadline": "投递截止时间",
}

EVENT_TYPE_PROGRESS_MAP = {
    "apply": "已投递",
    "exam": "机考",
    "interview1": "面试",
    "interview2": "面试",
    "interview3": "面试",
    "warm": "面试",
}


# ── Models ──────────────────────────────────────────────
class ApplicationRecord(BaseModel):
    company: str
    job: str
    city: str
    batch: Literal["秋招", "提前批"]
    apply_date: date | None = None
    exam_date: date | None = None
    interview1: date | None = None
    interview2: date | None = None
    interview3: date | None = None
    warm: date | None = None
    result_date: date | None = None
    deadline: date | None = None
    progress: Literal["已投递", "机考", "面试", "OC", "已挂", "放弃"]
    url: HttpUrl | None = None


class CompanyDetails(BaseModel):
    priority: Literal["⭐⭐⭐⭐⭐", "⭐⭐⭐⭐", "⭐⭐⭐", "⭐⭐", "⭐"]
    note: str = ""
    job_jd: str = ""


class TotalRecordUpdate(BaseModel):
    company: str
    job: str = ""
    city: str = ""
    batch: Literal["秋招", "提前批"]
    progress: Literal["未投递", "已投递", "机考", "面试", "OC", "已挂", "放弃"]
    directions: list[str] = []
    company_type: str = ""
    deadline: date | None = None
    url: str = ""
    priority: Literal["⭐⭐⭐⭐⭐", "⭐⭐⭐⭐", "⭐⭐⭐", "⭐⭐", "⭐"] = "⭐⭐⭐"
    note: str = Field(default="", max_length=5000)
    job_jd: str = Field(default="", max_length=10000)
    apply_date: date | None = None
    exam_date: date | None = None
    interview1: date | None = None
    interview2: date | None = None
    interview3: date | None = None
    warm: date | None = None
    result_date: date | None = None


class CalendarEventCreate(BaseModel):
    record_id: str
    event_type: Literal["apply", "exam", "interview1", "interview2", "interview3", "warm", "result", "deadline"]
    date: date


class LocalEventCreate(BaseModel):
    date: date
    label: str


class FeishuSyncRequest(BaseModel):
    url: str = Field(min_length=10, max_length=2000)


# ── Helpers ─────────────────────────────────────────────
def _application_fields(record: ApplicationRecord) -> dict:
    def date_ms(value: date | None):
        if value is None:
            return None
        china_tz = timezone(timedelta(hours=8))
        return int(datetime.combine(value, time.min, china_tz).timestamp() * 1000)

    return {
        "公司名称": record.company.strip(),
        "秋招岗位": record.job.strip(),
        "城市": record.city.strip(),
        "批次": record.batch,
        "投递时间": date_ms(record.apply_date),
        "机考时间": date_ms(record.exam_date),
        "一面": date_ms(record.interview1),
        "二面": date_ms(record.interview2),
        "三面": date_ms(record.interview3),
        "保温": date_ms(record.warm),
        "结果": record.result_date.isoformat() if record.result_date else None,
        "投递截止时间": date_ms(record.deadline),
        "进展": [record.progress],
        "投递链接": (
            {"link": str(record.url), "text": str(record.url)}
            if record.url else None
        ),
    }


def _total_record_fields(record: TotalRecordUpdate) -> dict:
    china_tz = timezone(timedelta(hours=8))
    def date_ms(value: date | None):
        return (
            int(datetime.combine(value, time.min, china_tz).timestamp() * 1000)
            if value else None
        )

    url = record.url.strip()
    directions = list(dict.fromkeys(item.strip() for item in record.directions if item.strip()))
    return {
        "公司名称": record.company.strip(),
        "秋招岗位": record.job.strip(),
        "城市": record.city.strip(),
        "批次": record.batch,
        "进展": [record.progress],
        "嵌入式方向": directions,
        "公司/行业类型": record.company_type.strip(),
        "投递截止时间": date_ms(record.deadline),
        "投递链接": {"link": url, "text": url} if url else None,
        "优先级": record.priority,
        "备注": record.note.strip(),
        "岗位JD": record.job_jd.strip(),
        "投递时间": date_ms(record.apply_date),
        "机考时间": date_ms(record.exam_date),
        "一面": date_ms(record.interview1),
        "二面": date_ms(record.interview2),
        "三面": date_ms(record.interview3),
        "保温": date_ms(record.warm),
        "结果": date_ms(record.result_date),
    }


def _empty(error: str) -> dict:
    return {
        "main": {
            "total_companies": 0,
            "exam_count": 0, "interview_count": 0, "offer_count": 0,
            "directions": [], "ctypes": [], "recent": [], "records": [],
        },
        "now": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "error": error,
    }


# ── Dashboard ───────────────────────────────────────────
@router.get("")
def get_dashboard(
    user: dict = Depends(auth_module.get_current_user),
):
    user_id = user["user_id"]
    cached = state.get_cache(user_id, max_age=30.0)
    if cached:
        return cached
    try:
        data = local_records.get_dashboard_data(user_id)
        state.set_cache(user_id, data)
        return data
    except Exception as e:
        stale = state.get_cache(user_id, max_age=1e9)
        if stale:
            return {**stale, "error": str(e), "stale": True}
        return _empty(str(e))


@router.post("/refresh")
def refresh_dashboard(
    user: dict = Depends(auth_module.get_current_user),
):
    user_id = user["user_id"]
    try:
        data = local_records.get_dashboard_data(user_id)
        state.set_cache(user_id, data)
        return data
    except Exception as e:
        stale = state.get_cache(user_id, max_age=1e9)
        if stale:
            return {**stale, "error": str(e), "stale": True}
        return _empty(str(e))


# ── Records CRUD ────────────────────────────────────────
@router.post("/records")
def save_application(
    record: ApplicationRecord,
    user: dict = Depends(auth_module.get_current_user),
):
    if not record.company.strip() or not record.job.strip() or not record.city.strip():
        raise HTTPException(status_code=422, detail="公司、目标岗位和城市不能为空")
    fields = _application_fields(record)
    try:
        local_records.create_record(user["user_id"], fields)
        data = local_records.get_dashboard_data(user["user_id"])
        state.set_cache(user["user_id"], data)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"本地记录保存失败：{exc}") from exc
    return {"success": True, "action": "created", "message": "已新增主表记录", "dashboard": data}


@router.post("/records/master")
def create_total_record(
    record: TotalRecordUpdate,
    user: dict = Depends(auth_module.get_current_user),
):
    if not record.company.strip():
        raise HTTPException(status_code=422, detail="公司不能为空")
    try:
        local_records.create_record(user["user_id"], _total_record_fields(record))
        data = local_records.get_dashboard_data(user["user_id"])
        state.set_cache(user["user_id"], data)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"总表记录保存失败：{exc}") from exc
    return {"success": True, "message": "已新增总表记录", "dashboard": data}


def _xlsx_response(content: bytes, filename: str) -> StreamingResponse:
    return StreamingResponse(
        BytesIO(content),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/records/template")
def download_total_record_template(
    user: dict = Depends(auth_module.get_current_user),
):
    return _xlsx_response(record_excel.build_template(), "total-records-template.xlsx")


@router.get("/records/export")
def export_total_records(
    user: dict = Depends(auth_module.get_current_user),
):
    records = local_records.list_records(user["user_id"])
    filename = f"total-records-{datetime.now(record_excel.CHINA_TZ).strftime('%Y%m%d-%H%M%S')}.xlsx"
    return _xlsx_response(record_excel.build_export(records), filename)


@router.post("/records/import")
async def import_total_records(
    file: UploadFile = File(...),
    user: dict = Depends(auth_module.get_current_user),
):
    filename = (file.filename or "").lower()
    if not filename.endswith(".xlsx"):
        raise HTTPException(status_code=422, detail="仅支持 .xlsx 格式的 Excel 文件")
    try:
        content = await file.read(record_excel.MAX_FILE_BYTES + 1)
        records = record_excel.parse_import(content)
        local_records.create_records(user["user_id"], records)
        data = local_records.get_dashboard_data(user["user_id"])
        state.set_cache(user["user_id"], data)
    except record_excel.ImportValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Excel 导入失败：{exc}") from exc
    finally:
        await file.close()
    return {
        "success": True,
        "imported_count": len(records),
        "message": f"成功导入 {len(records)} 条总表记录",
        "dashboard": data,
    }


@router.post("/records/feishu-sync")
def sync_feishu_records(
    body: FeishuSyncRequest,
    user: dict = Depends(auth_module.get_current_user),
):
    if not user.get("is_root"):
        raise HTTPException(status_code=403, detail="仅 root 用户可以同步飞书表格")
    try:
        source_rows = feishu_sync.read_table(body.url)
        existing = local_records.list_records(user["user_id"])
        additions, skipped, invalid = feishu_sync.prepare_sync(source_rows, existing)
        if additions:
            local_records.create_records(user["user_id"], additions)
        data = local_records.get_dashboard_data(user["user_id"])
        state.set_cache(user["user_id"], data)
    except feishu_sync.FeishuSyncError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"飞书同步失败：{exc}") from exc
    return {
        "success": True,
        "source_count": len(additions) + len(skipped),
        "scanned_count": len(source_rows),
        "added_count": len(additions),
        "skipped_count": len(skipped),
        "invalid_count": invalid,
        "skipped": skipped[:50],
        "message": f"同步完成：新增 {len(additions)} 条，跳过重复 {len(skipped)} 条",
        "dashboard": data,
    }


# ── GiveMeOC 同步 ──────────────────────────────────────

GIVEMEOC_LIST_URL = "https://www.givemeoc.com/wp-json/givemeoc/v1/companies"
GIVEMEOC_DETAIL_URL = "https://www.givemeoc.com/wp-json/givemeoc/v1/companies/{company_id}"
GIVEMEOC_HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Referer": "https://www.givemeoc.com/",
}
GIVEMEOC_MAX_WORKERS = 8

DATE_PATTERN = re.compile(r"(20\d{2})[-/.年](\d{1,2})[-/.月](\d{1,2})")

# In-memory sync progress store
_sync_progress: "dict[str, dict]" = {}

def _parse_givemeoc_deadline(deadline_str: str) -> int | None:
    """Convert givemeoc deadline string to millisecond timestamp."""
    if not deadline_str:
        return None
    text = str(deadline_str).strip()
    match = DATE_PATTERN.search(text)
    if not match:
        return None  # "招满为止", "长期有效" etc → no deadline
    try:
        parsed = datetime(int(match[1]), int(match[2]), int(match[3]))
        china_tz = timezone(timedelta(hours=8))
        return int(datetime.combine(parsed.date(), time.min, china_tz).timestamp() * 1000)
    except ValueError:
        return None


def _fetch_givemeoc_page(page: int) -> list[dict]:
    """Fetch one page from givemeoc list API."""
    resp = requests.get(
        GIVEMEOC_LIST_URL,
        params={"page": page, "per_page": 100, "order_by": "update_time", "order": "desc"},
        headers=GIVEMEOC_HEADERS,
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json().get("data", [])


def _fetch_givemeoc_detail(company_id: int) -> dict | None:
    """Fetch single company detail from givemeoc."""
    try:
        url = GIVEMEOC_DETAIL_URL.format(company_id=company_id)
        resp = requests.get(url, headers=GIVEMEOC_HEADERS, timeout=30)
        if resp.status_code == 200:
            return resp.json()
        return None
    except Exception:
        return None


def _to_shared_fields(givemeoc_detail: dict) -> dict:
    """Transform givemeoc detail dict to shared record fields dict."""
    locations = givemeoc_detail.get("locations") or []
    city = "; ".join(locations) if isinstance(locations, list) else str(locations or "")

    positions = givemeoc_detail.get("positions") or []
    job = "; ".join(positions) if isinstance(positions, list) else str(positions or "")

    related = givemeoc_detail.get("related_links") or []
    if isinstance(related, list) and related:
        url = related[0]
    elif isinstance(related, str) and related:
        url = related
    else:
        url = ""

    company_type_val = givemeoc_detail.get("type") or "未分类"

    directions = ["—"]

    batch = givemeoc_detail.get("recruitment_type", "秋招").strip() or "秋招"
    if "提前批" in batch:
        batch = "提前批"

    return {
        "公司名称": givemeoc_detail.get("name", "").strip(),
        "秋招岗位": job.strip(),
        "城市": city.strip(),
        "批次": batch,
        "嵌入式方向": directions,
        "公司/行业类型": (givemeoc_detail.get("industry") or "未分类").strip(),
        "投递链接": url.strip(),
        "投递截止时间": _parse_givemeoc_deadline(givemeoc_detail.get("deadline")),
    }


@router.post("/sync-from-givemeoc")
def sync_from_givemeoc(user: dict = Depends(auth_module.get_current_user)):
    """Root-only: start sync from givemeoc.com in background. Poll /progress for status."""
    if not user.get("is_root"):
        raise HTTPException(status_code=403, detail="仅 root 用户可以同步 GiveMeOC 数据")

    import threading

    sync_id = uuid.uuid4().hex[:12]
    _sync_progress[sync_id] = {
        "phase": "scanning",
        "found": 0,
        "done": 0,
        "total": 0,
        "added": 0,
        "skipped": 0,
        "errors": 0,
        "finished": False,
        "message": "正在扫描 givemeoc…",
    }

    def _run_sync():
        pid = _sync_progress[sync_id]
        bus.log("GiveMeOC 同步已启动", channel="sync", level="info")
        try:
            # Phase 1: collect IDs
            ids: list[int] = []
            page = 1
            while True:
                try:
                    rows = _fetch_givemeoc_page(page)
                except Exception:
                    break
                if not rows:
                    break
                for row in rows:
                    target = str(row.get("target_candidates") or "")
                    rec_type = str(row.get("recruitment_type") or "")
                    if "2027届" in target and "秋招" in rec_type and "春招" not in rec_type and "实习" not in rec_type:
                        ids.append(row["id"])
                page += 1
                pid["found"] = len(ids)
                if page % 10 == 0:
                    _time_module.sleep(0.2)

            if not ids:
                pid["finished"] = True
                pid["message"] = "未找到匹配 2027届 的岗位"
                return

            pid["phase"] = "syncing"
            pid["total"] = len(ids)
            pid["message"] = f"找到 {len(ids)} 条，正在获取详情…"

            # Phase 2: fetch details and insert
            def _sync_one(cid: int) -> tuple[int, int, int]:
                detail = _fetch_givemeoc_detail(cid)
                if not detail:
                    return 0, 0, 1
                fields = _to_shared_fields(detail)
                if not fields["公司名称"] or not fields["秋招岗位"] or not fields["投递链接"]:
                    return 0, 0, 1
                missing = local_records.shared_missing_fields(fields)
                if missing:
                    return 0, 0, 1
                try:
                    _, created = local_records.create_shared_record(user["user_id"], fields)
                    return (1, 0, 0) if created else (0, 1, 0)
                except Exception:
                    return 0, 0, 1

            with ThreadPoolExecutor(max_workers=GIVEMEOC_MAX_WORKERS) as executor:
                futures_map = {executor.submit(_sync_one, cid): cid for cid in ids}
                for future in as_completed(futures_map):
                    a, s, e = future.result()
                    pid["added"] += a
                    pid["skipped"] += s
                    pid["errors"] += e
                    pid["done"] += 1
                    if pid["done"] % 50 == 0:
                        _time_module.sleep(0.15)

            pid["finished"] = True
            pid["message"] = f"同步完成：新增 {pid['added']} 条，跳过重复 {pid['skipped']} 条"
            if pid["errors"]:
                pid["message"] += f"，失败 {pid['errors']} 条"
            bus.log(
                f"GiveMeOC 同步完成：新增 {pid['added']} / 跳过 {pid['skipped']} / 失败 {pid['errors']}",
                channel="sync", level="success" if pid["errors"] == 0 else "warn",
            )
        except Exception as exc:
            pid["finished"] = True
            pid["message"] = f"同步异常：{exc}"
            bus.log(f"GiveMeOC 同步异常：{exc}", channel="sync", level="error")

    threading.Thread(target=_run_sync, daemon=True).start()
    return {"success": True, "sync_id": sync_id, "message": "同步已启动"}


@router.get("/sync-from-givemeoc/progress")
def sync_from_givemeoc_progress(
    sync_id: str,
    user: dict = Depends(auth_module.get_current_user),
):
    """Poll sync progress."""
    if not (user.get("is_root") or user.get("is_admin")):
        raise HTTPException(status_code=403, detail="仅管理员可以查看同步进度")
    progress = _sync_progress.get(sync_id)
    if not progress:
        raise HTTPException(status_code=404, detail="未找到同步任务")
    return {"success": True, **progress}


# ── Auto-sync scheduler ──────────────────────────────

_scheduler_started = False


def _sync_scheduler_loop():
    """Background thread: check every 60s if auto-sync should fire."""
    import threading as _thr
    while True:
        _time_module.sleep(60)
        try:
            enabled = database.get_system_config("sync_enabled") or "0"
            if enabled != "1":
                continue
            sync_time = database.get_system_config("sync_time") or "04:00"
            now = datetime.now().strftime("%H:%M")
            if now == sync_time:
                # Run a full sync
                sync_id = uuid.uuid4().hex[:12]
                _sync_progress[sync_id] = {
                    "phase": "scanning", "found": 0, "done": 0, "total": 0,
                    "added": 0, "skipped": 0, "errors": 0,
                    "finished": False, "message": "自动同步中…",
                }
                # Reuse the same sync logic inline
                def _auto_sync():
                    pid = _sync_progress[sync_id]
                    bus.log("GiveMeOC 自动同步触发", channel="sync", level="info")
                    try:
                        ids = []
                        page = 1
                        while True:
                            try:
                                rows = _fetch_givemeoc_page(page)
                            except Exception:
                                break
                            if not rows:
                                break
                            for row in rows:
                                target = str(row.get("target_candidates") or "")
                                rec_type = str(row.get("recruitment_type") or "")
                                if "2027届" in target and "秋招" in rec_type and "春招" not in rec_type and "实习" not in rec_type:
                                    ids.append(row["id"])
                            page += 1
                            pid["found"] = len(ids)
                            if page % 10 == 0:
                                _time_module.sleep(0.2)
                        if not ids:
                            pid["finished"] = True
                            pid["message"] = "自动同步：未找到 2027届 岗位"
                            return
                        pid["phase"] = "syncing"
                        pid["total"] = len(ids)
                        def _sync_one(cid):
                            detail = _fetch_givemeoc_detail(cid)
                            if not detail:
                                return 0, 0, 1
                            fields = _to_shared_fields(detail)
                            if not fields["公司名称"] or not fields["秋招岗位"] or not fields["投递链接"]:
                                return 0, 0, 1
                            missing = local_records.shared_missing_fields(fields)
                            if missing:
                                return 0, 0, 1
                            try:
                                _, created = local_records.create_shared_record(2, fields)
                                return (1, 0, 0) if created else (0, 1, 0)
                            except Exception:
                                return 0, 0, 1
                        with ThreadPoolExecutor(max_workers=GIVEMEOC_MAX_WORKERS) as executor:
                            futures_map = {executor.submit(_sync_one, cid): cid for cid in ids}
                            for future in as_completed(futures_map):
                                a, s, e = future.result()
                                pid["added"] += a
                                pid["skipped"] += s
                                pid["errors"] += e
                                pid["done"] += 1
                        pid["finished"] = True
                        pid["message"] = f"自动同步完成：新增 {pid['added']} 条，跳过 {pid['skipped']} 条"
                        bus.log(
                            f"自动同步完成：新增 {pid['added']} / 跳过 {pid['skipped']} / 失败 {pid['errors']}",
                            channel="sync", level="success" if pid["errors"] == 0 else "warn",
                        )
                    except Exception as exc:
                        pid["finished"] = True
                        pid["message"] = f"自动同步异常：{exc}"
                        bus.log(f"自动同步异常：{exc}", channel="sync", level="error")
                _thr.Thread(target=_auto_sync, daemon=True).start()
        except Exception:
            pass


def start_sync_scheduler():
    global _scheduler_started
    if _scheduler_started:
        return
    _scheduler_started = True
    import threading as _thr
    _thr.Thread(target=_sync_scheduler_loop, daemon=True).start()


@router.get("/admin/sync-schedule")
def get_sync_schedule(user: dict = Depends(auth_module.get_current_user)):
    """Get current auto-sync schedule settings."""
    if not (user.get("is_root") or user.get("is_admin")):
        raise HTTPException(status_code=403, detail="仅管理员可以查看同步计划")
    return {
        "success": True,
        "enabled": (database.get_system_config("sync_enabled") or "0") == "1",
        "time": database.get_system_config("sync_time") or "04:00",
    }


class SyncScheduleBody(BaseModel):
    enabled: bool = False
    time: str = "04:00"


@router.post("/admin/sync-schedule")
def set_sync_schedule(
    body: SyncScheduleBody,
    user: dict = Depends(auth_module.get_current_user),
):
    """Set auto-sync schedule."""
    if not user.get("is_root"):
        raise HTTPException(status_code=403, detail="仅 root 用户可以修改同步计划")
    if not re.match(r"^\d{2}:\d{2}$", body.time):
        raise HTTPException(status_code=422, detail="时间格式需为 HH:MM")
    database.set_system_config("sync_enabled", "1" if body.enabled else "0")
    database.set_system_config("sync_time", body.time)
    return {
        "success": True,
        "message": f"自动同步{'已启用' if body.enabled else '已禁用'}，时间 {body.time}",
        "enabled": body.enabled,
        "time": body.time,
    }


# ── Shared total table ─────────────────────────────────
@router.get("/shared/records")
def get_shared_records(
    user: dict = Depends(auth_module.get_current_user),
):
    return {
        "records": local_records.list_shared_records(user["user_id"]),
        "can_delete": bool(user.get("is_admin")),
    }


@router.post("/shared/records")
def create_shared_record(
    record: TotalRecordUpdate,
    user: dict = Depends(auth_module.get_current_user),
):
    if not user.get("is_admin"):
        raise HTTPException(status_code=403, detail="普通用户无权直接新建共享记录")
    try:
        shared_record, created = local_records.create_shared_record(
            user["user_id"], _total_record_fields(record)
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"新建共享记录失败：{exc}") from exc
    return {
        "success": True,
        "created": created,
        "record": shared_record,
        "message": "共享记录已新建" if created else "共享总表中已存在相同记录",
    }


@router.post("/shared/records/from-personal/{record_id}")
def upload_record_to_shared(
    record_id: str,
    user: dict = Depends(auth_module.get_current_user),
):
    if not record_id.startswith("rec"):
        raise HTTPException(status_code=422, detail="无效的个人记录 ID")
    try:
        shared_record, created = local_records.publish_shared_record(
            user["user_id"], record_id
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"上传共享总表失败：{exc}") from exc
    return {
        "success": True,
        "created": created,
        "record": shared_record,
        "message": "已上传到共享总表" if created else "共享总表中已存在相同记录",
    }


@router.post("/shared/records/{shared_id}/copy")
def copy_shared_to_personal(
    shared_id: str,
    user: dict = Depends(auth_module.get_current_user),
):
    if not shared_id.startswith("shr"):
        raise HTTPException(status_code=422, detail="无效的共享记录 ID")
    try:
        record_id, created = local_records.copy_shared_record(
            user["user_id"], shared_id
        )
        data = local_records.get_dashboard_data(user["user_id"])
        state.set_cache(user["user_id"], data)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"添加到个人总表失败：{exc}") from exc
    return {
        "success": True,
        "created": created,
        "record_id": record_id,
        "message": "已添加到个人总表" if created else "个人总表中已存在该记录",
        "dashboard": data,
    }


@router.delete("/shared/records/{shared_id}")
@router.post("/shared/records/{shared_id}/delete")
def remove_shared_record(
    shared_id: str,
    user: dict = Depends(auth_module.get_current_user),
):
    if not user.get("is_admin"):
        raise HTTPException(status_code=403, detail="普通用户无权删除共享总表记录")
    if not shared_id.startswith("shr"):
        raise HTTPException(status_code=422, detail="无效的共享记录 ID")
    try:
        if not local_records.delete_shared_record(shared_id):
            raise HTTPException(status_code=404, detail="未找到对应的共享记录")
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"删除共享记录失败：{exc}") from exc
    return {"success": True, "message": "共享记录已删除"}


@router.put("/records/{record_id}")
@router.post("/records/{record_id}/update")
def edit_application(
    record_id: str,
    record: ApplicationRecord,
    user: dict = Depends(auth_module.get_current_user),
):
    if not record_id.startswith("rec"):
        raise HTTPException(status_code=422, detail="无效的本地记录 ID")
    if not record.company.strip() or not record.job.strip() or not record.city.strip():
        raise HTTPException(status_code=422, detail="公司、目标岗位和城市不能为空")
    try:
        if not local_records.update_record(user["user_id"], record_id, _application_fields(record)):
            raise HTTPException(status_code=404, detail="未找到对应的本地记录")
        data = local_records.get_dashboard_data(user["user_id"])
        state.set_cache(user["user_id"], data)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"本地记录更新失败：{exc}") from exc
    return {"success": True, "message": "投递记录已更新", "dashboard": data}


@router.delete("/records/{record_id}")
@router.post("/records/{record_id}/remove")
def remove_application(
    record_id: str,
    user: dict = Depends(auth_module.get_current_user),
):
    if not record_id.startswith("rec"):
        raise HTTPException(status_code=422, detail="无效的本地记录 ID")
    try:
        updated = local_records.update_record(user["user_id"], record_id, {
            "进展": ["未投递"], "投递时间": None, "机考时间": None,
            "一面": None, "二面": None, "三面": None, "保温": None, "结果": None,
        })
        if not updated:
            raise HTTPException(status_code=404, detail="未找到对应的本地记录")
        data = local_records.get_dashboard_data(user["user_id"])
        state.set_cache(user["user_id"], data)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"本地记录更新失败：{exc}") from exc
    return {"success": True, "message": "已移出投递记录并重置投递流程", "dashboard": data}


@router.delete("/records/{record_id}/permanent")
@router.post("/records/{record_id}/permanent-delete")
def permanently_delete_record(
    record_id: str,
    user: dict = Depends(auth_module.get_current_user),
):
    if not record_id.startswith("rec"):
        raise HTTPException(status_code=422, detail="无效的本地记录 ID")
    try:
        if not local_records.delete_record(user["user_id"], record_id):
            raise HTTPException(status_code=404, detail="未找到对应的本地记录")
        data = local_records.get_dashboard_data(user["user_id"])
        state.set_cache(user["user_id"], data)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"本地记录删除失败：{exc}") from exc
    return {"success": True, "message": "总表记录已永久删除", "dashboard": data}


@router.put("/records/{record_id}/master")
@router.post("/records/{record_id}/master/update")
def edit_total_record(
    record_id: str,
    record: TotalRecordUpdate,
    user: dict = Depends(auth_module.get_current_user),
):
    if not record_id.startswith("rec"):
        raise HTTPException(status_code=422, detail="无效的本地记录 ID")
    if not record.company.strip():
        raise HTTPException(status_code=422, detail="公司不能为空")
    try:
        if not local_records.update_record(
            user["user_id"], record_id, _total_record_fields(record)
        ):
            raise HTTPException(status_code=404, detail="未找到对应的本地记录")
        data = local_records.get_dashboard_data(user["user_id"])
        state.set_cache(user["user_id"], data)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"本地记录更新失败：{exc}") from exc
    return {"success": True, "message": "总表记录已更新", "dashboard": data}


@router.post("/records/{record_id}/apply")
def add_to_applications(
    record_id: str,
    user: dict = Depends(auth_module.get_current_user),
):
    if not record_id.startswith("rec"):
        raise HTTPException(status_code=422, detail="无效的本地记录 ID")
    try:
        record = local_records.get_record(user["user_id"], record_id)
        if not record:
            raise HTTPException(status_code=404, detail="未找到对应的总表记录")
        current_fields = record.get("fields") or {}
        if not current_fields.get("投递时间"):
            local_records.update_record(user["user_id"], record_id, {
                "进展": ["已投递"],
                "投递时间": int(datetime.now(timezone.utc).timestamp() * 1000),
            })
            message = "已加入投递记录"
        else:
            message = "该记录已在投递记录中"
        data = local_records.get_dashboard_data(user["user_id"])
        state.set_cache(user["user_id"], data)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"本地记录更新失败：{exc}") from exc
    return {"success": True, "message": message, "dashboard": data}


@router.post("/records/{record_id}/details")
def save_company_details(
    record_id: str,
    details: CompanyDetails,
    user: dict = Depends(auth_module.get_current_user),
):
    if not record_id.startswith("rec"):
        raise HTTPException(status_code=422, detail="无效的本地记录 ID")
    try:
        updated = local_records.update_record(user["user_id"], record_id, {
            "优先级": details.priority,
            "备注": details.note.strip(),
            "岗位JD": details.job_jd.strip(),
        })
        if not updated:
            raise HTTPException(status_code=404, detail="未找到对应的本地记录")
        data = local_records.get_dashboard_data(user["user_id"])
        state.set_cache(user["user_id"], data)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"本地记录更新失败：{exc}") from exc
    return {"success": True, "message": "公司信息已更新", "dashboard": data}


# ── 记录日历字段 ─────────────────────────────────────────
@router.post("/calendar/event")
def create_calendar_event(
    event: CalendarEventCreate,
    user: dict = Depends(auth_module.get_current_user),
):
    if not event.record_id.startswith("rec"):
        raise HTTPException(status_code=422, detail="无效的本地记录 ID")

    china_tz = timezone(timedelta(hours=8))
    ts = int(datetime.combine(event.date, time.min, china_tz).timestamp() * 1000)
    field_name = EVENT_TYPE_FIELD_MAP.get(event.event_type)
    if not field_name:
        raise HTTPException(status_code=422, detail=f"未知事件类型: {event.event_type}")

    fields: dict = {field_name: ts}
    progress_label = EVENT_TYPE_PROGRESS_MAP.get(event.event_type)
    if progress_label:
        try:
            record = local_records.get_record(user["user_id"], event.record_id)
            if record:
                current_progress = (record.get("fields") or {}).get("进展") or []
                progress_order = ["未投递", "已投递", "机考", "面试", "OC", "已挂", "放弃"]
                current_idx = max(
                    (progress_order.index(p) for p in current_progress if p in progress_order),
                    default=-1,
                )
                new_idx = progress_order.index(progress_label) if progress_label in progress_order else -1
                if new_idx > current_idx:
                    fields["进展"] = [progress_label]
        except Exception:
            pass

    try:
        if not local_records.update_record(user["user_id"], event.record_id, fields):
            raise HTTPException(status_code=404, detail="未找到对应的本地记录")
        data = local_records.get_dashboard_data(user["user_id"])
        state.set_cache(user["user_id"], data)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"本地日程保存失败：{exc}") from exc
    return {"success": True, "message": f"已为记录添加「{field_name}」日程", "dashboard": data}


# ── 本地日程（per-user）─────────────────────────────────
@router.post("/calendar/local-event")
def create_local_event(
    event: LocalEventCreate,
    user: dict = Depends(auth_module.get_current_user),
):
    label = (event.label or "").strip()
    if not label:
        raise HTTPException(status_code=422, detail="日程内容不能为空")
    event_id = uuid.uuid4().hex[:12]
    database.add_local_event(user["user_id"], event_id, event.date.isoformat(), label)
    return {
        "success": True,
        "message": f"已添加本地日程「{label}」",
        "event": {"id": event_id, "date": event.date.isoformat(), "label": label},
    }


@router.get("/calendar/local-events")
def list_local_events(user: dict = Depends(auth_module.get_current_user)):
    return {"events": database.get_local_events(user["user_id"])}


@router.delete("/calendar/local-event/{event_id}")
@router.post("/calendar/local-event/{event_id}/delete")
def delete_local_event(
    event_id: str,
    user: dict = Depends(auth_module.get_current_user),
):
    ok = database.delete_local_event(user["user_id"], event_id)
    if not ok:
        raise HTTPException(status_code=404, detail="未找到该本地日程")
    return {"success": True, "message": "本地日程已删除"}


class CalendarEventDelete(BaseModel):
    record_id: str
    event_type: Literal["apply", "exam", "interview1", "interview2", "interview3", "warm", "result", "deadline"]


@router.delete("/calendar/event")
@router.post("/calendar/event/delete")
def delete_calendar_event(
    body: CalendarEventDelete,
    user: dict = Depends(auth_module.get_current_user),
):
    """删除本地记录上的某个日程（将对应日期字段设为空）。"""
    if not body.record_id.startswith("rec"):
        raise HTTPException(status_code=422, detail="无效的本地记录 ID")
    field_name = EVENT_TYPE_FIELD_MAP.get(body.event_type)
    if not field_name:
        raise HTTPException(status_code=422, detail=f"未知事件类型: {body.event_type}")
    try:
        if not local_records.update_record(user["user_id"], body.record_id, {field_name: None}):
            raise HTTPException(status_code=404, detail="未找到对应的本地记录")
        data = local_records.get_dashboard_data(user["user_id"])
        state.set_cache(user["user_id"], data)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"本地日程删除失败：{exc}") from exc
    return {"success": True, "message": f"已删除「{field_name}」日程", "dashboard": data}
