"""看板数据接口：GET /api/dashboard 返回主表统计。
"""
import json
import uuid
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, HttpUrl

from app import feishu, state

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])

LOCAL_EVENTS_FILE = Path(__file__).parent.parent.parent / "data" / "calendar_events.json"


def _load_local_events() -> list[dict]:
    """加载本地日程文件，不存在或格式错误时返回空列表。"""
    if not LOCAL_EVENTS_FILE.exists():
        return []
    try:
        with open(LOCAL_EVENTS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except (json.JSONDecodeError, OSError):
        return []


def _save_local_events(events: list[dict]) -> None:
    """将日程列表写入本地 JSON 文件。"""
    LOCAL_EVENTS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(LOCAL_EVENTS_FILE, "w", encoding="utf-8", newline="\n") as f:
        json.dump(events, f, ensure_ascii=False, indent=2)


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
    """飞书不可达时的降级空数据，结构与正常返回一致，附带 error 供前端提示。"""
    return {
        "main": {
            "total_companies": 0,
            "exam_count": 0, "interview_count": 0, "offer_count": 0,
            "directions": [], "ctypes": [], "recent": [], "records": [],
        },
        "now": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "error": error,
    }


@router.get("")
def get_dashboard():
    # 30 秒缓存，减少飞书 API 压力
    cached = state.get_cache(max_age=30.0)
    if cached:
        return cached
    try:
        data = feishu.get_dashboard_data()
        state.set_cache(data)
        return data
    except Exception as e:
        # 有旧缓存就返回旧缓存 + 提示；否则返回空结构 + 提示。
        stale = state.get_cache(max_age=1e9)
        if stale:
            return {**stale, "error": feishu.friendly_error(e), "stale": True}
        return _empty(feishu.friendly_error(e))


@router.post("/refresh")
def refresh_dashboard():
    try:
        data = feishu.get_dashboard_data()
        state.set_cache(data)
        return data
    except Exception as e:
        stale = state.get_cache(max_age=1e9)
        if stale:
            return {**stale, "error": feishu.friendly_error(e), "stale": True}
        return _empty(feishu.friendly_error(e))


@router.post("/records")
def save_application(record: ApplicationRecord):
    if not record.company.strip() or not record.job.strip() or not record.city.strip():
        raise HTTPException(status_code=422, detail="公司、目标岗位和城市不能为空")
    fields = _application_fields(record)
    try:
        result = feishu.create_application(fields)
        data = feishu.get_dashboard_data()
        state.set_cache(data)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=feishu.friendly_error(exc)) from exc
    return {
        "success": True,
        "action": "created",
        "message": "已新增主表记录",
        "dashboard": data,
    }


@router.put("/records/{record_id}")
def edit_application(record_id: str, record: ApplicationRecord):
    if not record_id.startswith("rec"):
        raise HTTPException(status_code=422, detail="无效的飞书记录 ID")
    if not record.company.strip() or not record.job.strip() or not record.city.strip():
        raise HTTPException(status_code=422, detail="公司、目标岗位和城市不能为空")
    try:
        feishu.update_record(record_id, _application_fields(record))
        data = feishu.get_dashboard_data()
        state.set_cache(data)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=feishu.friendly_error(exc)) from exc
    return {"success": True, "message": "投递记录已更新", "dashboard": data}


@router.delete("/records/{record_id}")
def remove_application(record_id: str):
    if not record_id.startswith("rec"):
        raise HTTPException(status_code=422, detail="无效的飞书记录 ID")
    try:
        feishu.update_record(
            record_id,
            {
                "进展": ["未投递"],
                "投递时间": None,
                "机考时间": None,
                "一面": None,
                "二面": None,
                "三面": None,
                "保温": None,
                "结果": None,
            },
        )
        data = feishu.get_dashboard_data()
        state.set_cache(data)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=feishu.friendly_error(exc)) from exc
    return {"success": True, "message": "已移出投递记录并重置投递流程", "dashboard": data}


@router.delete("/records/{record_id}/permanent")
def permanently_delete_record(record_id: str):
    if not record_id.startswith("rec"):
        raise HTTPException(status_code=422, detail="无效的飞书记录 ID")
    try:
        feishu.delete_record(record_id)
        data = feishu.get_dashboard_data()
        state.set_cache(data)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=feishu.friendly_error(exc)) from exc
    return {"success": True, "message": "总表记录已永久删除", "dashboard": data}


@router.put("/records/{record_id}/master")
def edit_total_record(record_id: str, record: TotalRecordUpdate):
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
        state.set_cache(data)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=feishu.friendly_error(exc)) from exc
    return {"success": True, "message": "总表记录已更新", "dashboard": data}


@router.post("/records/{record_id}/apply")
def add_to_applications(record_id: str):
    if not record_id.startswith("rec"):
        raise HTTPException(status_code=422, detail="无效的飞书记录 ID")
    try:
        record = next(
            (item for item in feishu.list_records(feishu.MAIN_TABLE_ID) if item.get("record_id") == record_id),
            None,
        )
        if not record:
            raise HTTPException(status_code=404, detail="未找到对应的总表记录")
        current_fields = record.get("fields") or {}
        if not current_fields.get("投递时间"):
            feishu.update_record(
                record_id,
                {
                    "进展": ["已投递"],
                    "投递时间": int(datetime.now(timezone.utc).timestamp() * 1000),
                },
            )
            message = "已加入投递记录"
        else:
            message = "该记录已在投递记录中"
        data = feishu.get_dashboard_data()
        state.set_cache(data)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=502, detail=feishu.friendly_error(exc)) from exc
    return {"success": True, "message": message, "dashboard": data}


# ── 日历日程管理 ────────────────────────────────────────
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


class CalendarEventCreate(BaseModel):
    record_id: str
    event_type: Literal["apply", "exam", "interview1", "interview2", "interview3", "warm", "result", "deadline"]
    date: date


@router.post("/calendar/event")
def create_calendar_event(event: CalendarEventCreate):
    """在日历上为已有总表记录新建/更新日程日期。

    根据 event_type 将日期写入对应的飞书字段，并自动推进进展状态。
    """
    if not event.record_id.startswith("rec"):
        raise HTTPException(status_code=422, detail="无效的飞书记录 ID")

    china_tz = timezone(timedelta(hours=8))
    ts = int(datetime.combine(event.date, time.min, china_tz).timestamp() * 1000)

    field_name = EVENT_TYPE_FIELD_MAP.get(event.event_type)
    if not field_name:
        raise HTTPException(status_code=422, detail=f"未知事件类型: {event.event_type}")

    fields: dict = {field_name: ts}

    # 自动推进进展状态（仅当当前进展较低时）
    progress_label = EVENT_TYPE_PROGRESS_MAP.get(event.event_type)
    if progress_label:
        try:
            record = next(
                (item for item in feishu.list_records(feishu.MAIN_TABLE_ID)
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
            pass  # 进展推进失败不影响日期写入

    try:
        feishu.update_record(event.record_id, fields)
        data = feishu.get_dashboard_data()
        state.set_cache(data)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=feishu.friendly_error(exc)) from exc

    return {
        "success": True,
        "message": f"已为记录添加「{field_name}」日程",
        "dashboard": data,
    }


# ── 本地日程管理（"其他"类型，无需绑定公司）──────────────
class LocalEventCreate(BaseModel):
    date: date
    label: str


class LocalEvent(BaseModel):
    id: str
    date: date
    label: str


@router.post("/calendar/local-event")
def create_local_event(event: LocalEventCreate):
    """新建本地日程，不写入飞书，无需关联公司。"""
    label = (event.label or "").strip()
    if not label:
        raise HTTPException(status_code=422, detail="日程内容不能为空")
    events = _load_local_events()
    new_event = {
        "id": uuid.uuid4().hex[:12],
        "date": event.date.isoformat(),
        "label": label,
    }
    events.append(new_event)
    _save_local_events(events)
    return {
        "success": True,
        "message": f"已添加本地日程「{label}」",
        "event": new_event,
    }


@router.get("/calendar/local-events")
def list_local_events():
    """返回所有本地日程。"""
    return {"events": _load_local_events()}


@router.delete("/calendar/local-event/{event_id}")
def delete_local_event(event_id: str):
    """删除指定本地日程。"""
    events = _load_local_events()
    before = len(events)
    events = [e for e in events if e.get("id") != event_id]
    if len(events) == before:
        raise HTTPException(status_code=404, detail="未找到该本地日程")
    _save_local_events(events)
    return {"success": True, "message": "本地日程已删除"}


@router.post("/records/{record_id}/details")
def save_company_details(record_id: str, details: CompanyDetails):
    if not record_id.startswith("rec"):
        raise HTTPException(status_code=422, detail="无效的飞书记录 ID")
    try:
        feishu.update_record(
            record_id,
            {
                "优先级": details.priority,
                "备注": details.note.strip(),
                "岗位JD": details.job_jd.strip(),
            },
        )
        data = feishu.get_dashboard_data()
        state.set_cache(data)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=feishu.friendly_error(exc)) from exc
    return {"success": True, "message": "公司信息已更新", "dashboard": data}
