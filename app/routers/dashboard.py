"""看板数据接口：GET /api/dashboard 返回主表统计。
"""
from datetime import date, datetime, time, timedelta, timezone
from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, HttpUrl

from app import feishu, state

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


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
        feishu.delete_record(record_id)
        data = feishu.get_dashboard_data()
        state.set_cache(data)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=feishu.friendly_error(exc)) from exc
    return {"success": True, "message": "投递记录已删除", "dashboard": data}


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
