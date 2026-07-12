"""看板数据接口：per-user 读写飞书 + 本地日程。"""
import uuid
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, HttpUrl

from app import auth as auth_module, database, feishu, state

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


# ── 请求级配置注入 ──────────────────────────────────────
def _use_feishu(user: dict = Depends(auth_module.get_current_user)):
    """依赖：为当前请求设置用户专属飞书配置。"""
    cfg = database.get_user_config(user["user_id"])
    feishu.set_request_config({
        "APP_ID": cfg.get("feishu_app_id", ""),
        "APP_SECRET": cfg.get("feishu_app_secret", ""),
        "APP_TOKEN": cfg.get("feishu_app_token", ""),
        "MAIN_TABLE_ID": cfg.get("main_table_id", ""),
        "DEEPSEEK_API_KEY": cfg.get("deepseek_api_key", ""),
        "DEEPSEEK_MODEL": cfg.get("deepseek_model", "deepseek-v4-flash"),
    })
    return cfg


# ── Models ──────────────────────────────────────────────
class ApplicationRecord(BaseModel):
    company: str
    job: str
    city: str
    batch: Literal["秋招", "提前批"]
    apply_date: date
    exam_date: date | None = None
    interview1: date | None = None
    interview2: date | None = None
    interview3: date | None = None
    warm: date | None = None
    result_date: date | None = None
    deadline: date | None = None
    progress: Literal["已投递", "机考", "面试", "OC", "已挂", "放弃"]
    url: HttpUrl


class CompanyDetails(BaseModel):
    priority: Literal["⭐⭐⭐⭐⭐", "⭐⭐⭐⭐", "⭐⭐⭐", "⭐⭐", "⭐"]
    note: str = ""
    job_jd: str = ""


class TotalRecordUpdate(BaseModel):
    company: str
    job: str
    city: str = ""
    batch: Literal["秋招", "提前批"]
    progress: Literal["未投递", "已投递", "机考", "面试", "OC", "已挂", "放弃"]
    deadline: date | None = None
    url: str = ""


class CalendarEventCreate(BaseModel):
    record_id: str
    event_type: Literal["apply", "exam", "interview1", "interview2", "interview3", "warm", "result", "deadline"]
    date: date


class LocalEventCreate(BaseModel):
    date: date
    label: str


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
        "投递链接": {"link": str(record.url), "text": str(record.url)},
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
    _cfg=Depends(_use_feishu),
):
    user_id = user["user_id"]
    cached = state.get_cache(user_id, max_age=30.0)
    if cached:
        return cached
    try:
        data = feishu.get_dashboard_data()
        state.set_cache(user_id, data)
        return data
    except Exception as e:
        stale = state.get_cache(user_id, max_age=1e9)
        if stale:
            return {**stale, "error": feishu.friendly_error(e), "stale": True}
        return _empty(feishu.friendly_error(e))


@router.post("/refresh")
def refresh_dashboard(
    user: dict = Depends(auth_module.get_current_user),
    _cfg=Depends(_use_feishu),
):
    user_id = user["user_id"]
    try:
        data = feishu.get_dashboard_data()
        state.set_cache(user_id, data)
        return data
    except Exception as e:
        stale = state.get_cache(user_id, max_age=1e9)
        if stale:
            return {**stale, "error": feishu.friendly_error(e), "stale": True}
        return _empty(feishu.friendly_error(e))


# ── Records CRUD ────────────────────────────────────────
@router.post("/records")
def save_application(
    record: ApplicationRecord,
    user: dict = Depends(auth_module.get_current_user),
    _cfg=Depends(_use_feishu),
):
    if not record.company.strip() or not record.job.strip() or not record.city.strip():
        raise HTTPException(status_code=422, detail="公司、目标岗位和城市不能为空")
    fields = _application_fields(record)
    try:
        result = feishu.create_application(fields)
        data = feishu.get_dashboard_data()
        state.set_cache(user["user_id"], data)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=feishu.friendly_error(exc)) from exc
    return {"success": True, "action": "created", "message": "已新增主表记录", "dashboard": data}


@router.put("/records/{record_id}")
def edit_application(
    record_id: str,
    record: ApplicationRecord,
    user: dict = Depends(auth_module.get_current_user),
    _cfg=Depends(_use_feishu),
):
    if not record_id.startswith("rec"):
        raise HTTPException(status_code=422, detail="无效的飞书记录 ID")
    if not record.company.strip() or not record.job.strip() or not record.city.strip():
        raise HTTPException(status_code=422, detail="公司、目标岗位和城市不能为空")
    try:
        feishu.update_record(record_id, _application_fields(record))
        data = feishu.get_dashboard_data()
        state.set_cache(user["user_id"], data)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=feishu.friendly_error(exc)) from exc
    return {"success": True, "message": "投递记录已更新", "dashboard": data}


@router.delete("/records/{record_id}")
def remove_application(
    record_id: str,
    user: dict = Depends(auth_module.get_current_user),
    _cfg=Depends(_use_feishu),
):
    if not record_id.startswith("rec"):
        raise HTTPException(status_code=422, detail="无效的飞书记录 ID")
    try:
        feishu.update_record(record_id, {
            "进展": ["未投递"], "投递时间": None, "机考时间": None,
            "一面": None, "二面": None, "三面": None, "保温": None, "结果": None,
        })
        data = feishu.get_dashboard_data()
        state.set_cache(user["user_id"], data)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=feishu.friendly_error(exc)) from exc
    return {"success": True, "message": "已移出投递记录并重置投递流程", "dashboard": data}


@router.delete("/records/{record_id}/permanent")
def permanently_delete_record(
    record_id: str,
    user: dict = Depends(auth_module.get_current_user),
    _cfg=Depends(_use_feishu),
):
    if not record_id.startswith("rec"):
        raise HTTPException(status_code=422, detail="无效的飞书记录 ID")
    try:
        feishu.delete_record(record_id)
        data = feishu.get_dashboard_data()
        state.set_cache(user["user_id"], data)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=feishu.friendly_error(exc)) from exc
    return {"success": True, "message": "总表记录已永久删除", "dashboard": data}


@router.put("/records/{record_id}/master")
def edit_total_record(
    record_id: str,
    record: TotalRecordUpdate,
    user: dict = Depends(auth_module.get_current_user),
    _cfg=Depends(_use_feishu),
):
    if not record_id.startswith("rec"):
        raise HTTPException(status_code=422, detail="无效的飞书记录 ID")
    if not record.company.strip() or not record.job.strip():
        raise HTTPException(status_code=422, detail="公司和目标岗位不能为空")
    china_tz = timezone(timedelta(hours=8))
    deadline = (
        int(datetime.combine(record.deadline, time.min, china_tz).timestamp() * 1000)
        if record.deadline else None
    )
    url = record.url.strip()
    fields = {
        "公司名称": record.company.strip(),
        "秋招岗位": record.job.strip(),
        "城市": record.city.strip(),
        "批次": record.batch,
        "进展": [record.progress],
        "投递截止时间": deadline,
        "投递链接": {"link": url, "text": url} if url else None,
    }
    try:
        feishu.update_record(record_id, fields)
        data = feishu.get_dashboard_data()
        state.set_cache(user["user_id"], data)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=feishu.friendly_error(exc)) from exc
    return {"success": True, "message": "总表记录已更新", "dashboard": data}


@router.post("/records/{record_id}/apply")
def add_to_applications(
    record_id: str,
    user: dict = Depends(auth_module.get_current_user),
    _cfg=Depends(_use_feishu),
):
    if not record_id.startswith("rec"):
        raise HTTPException(status_code=422, detail="无效的飞书记录 ID")
    try:
        record = next(
            (item for item in feishu.list_records(database.get_user_config(user["user_id"]).get("main_table_id", ""))
             if item.get("record_id") == record_id),
            None,
        )
        if not record:
            raise HTTPException(status_code=404, detail="未找到对应的总表记录")
        current_fields = record.get("fields") or {}
        if not current_fields.get("投递时间"):
            feishu.update_record(record_id, {
                "进展": ["已投递"],
                "投递时间": int(datetime.now(timezone.utc).timestamp() * 1000),
            })
            message = "已加入投递记录"
        else:
            message = "该记录已在投递记录中"
        data = feishu.get_dashboard_data()
        state.set_cache(user["user_id"], data)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=502, detail=feishu.friendly_error(exc)) from exc
    return {"success": True, "message": message, "dashboard": data}


@router.post("/records/{record_id}/details")
def save_company_details(
    record_id: str,
    details: CompanyDetails,
    user: dict = Depends(auth_module.get_current_user),
    _cfg=Depends(_use_feishu),
):
    if not record_id.startswith("rec"):
        raise HTTPException(status_code=422, detail="无效的飞书记录 ID")
    try:
        feishu.update_record(record_id, {
            "优先级": details.priority,
            "备注": details.note.strip(),
            "岗位JD": details.job_jd.strip(),
        })
        data = feishu.get_dashboard_data()
        state.set_cache(user["user_id"], data)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=feishu.friendly_error(exc)) from exc
    return {"success": True, "message": "公司信息已更新", "dashboard": data}


# ── 日历日程（飞书字段）──────────────────────────────────
@router.post("/calendar/event")
def create_calendar_event(
    event: CalendarEventCreate,
    user: dict = Depends(auth_module.get_current_user),
    _cfg=Depends(_use_feishu),
):
    if not event.record_id.startswith("rec"):
        raise HTTPException(status_code=422, detail="无效的飞书记录 ID")

    china_tz = timezone(timedelta(hours=8))
    ts = int(datetime.combine(event.date, time.min, china_tz).timestamp() * 1000)
    field_name = EVENT_TYPE_FIELD_MAP.get(event.event_type)
    if not field_name:
        raise HTTPException(status_code=422, detail=f"未知事件类型: {event.event_type}")

    fields: dict = {field_name: ts}
    progress_label = EVENT_TYPE_PROGRESS_MAP.get(event.event_type)
    if progress_label:
        try:
            table_id = database.get_user_config(user["user_id"]).get("main_table_id", "")
            record = next(
                (item for item in feishu.list_records(table_id)
                 if item.get("record_id") == event.record_id),
                None,
            )
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
        feishu.update_record(event.record_id, fields)
        data = feishu.get_dashboard_data()
        state.set_cache(user["user_id"], data)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=feishu.friendly_error(exc)) from exc
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
def delete_calendar_event(
    body: CalendarEventDelete,
    user: dict = Depends(auth_module.get_current_user),
    _cfg=Depends(_use_feishu),
):
    """删除飞书记录上的某个日程（将对应日期字段设为空）。"""
    if not body.record_id.startswith("rec"):
        raise HTTPException(status_code=422, detail="无效的飞书记录 ID")
    field_name = EVENT_TYPE_FIELD_MAP.get(body.event_type)
    if not field_name:
        raise HTTPException(status_code=422, detail=f"未知事件类型: {body.event_type}")
    try:
        feishu.update_record(body.record_id, {field_name: None})
        data = feishu.get_dashboard_data()
        state.set_cache(user["user_id"], data)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=feishu.friendly_error(exc)) from exc
    return {"success": True, "message": f"已删除「{field_name}」日程", "dashboard": data}
