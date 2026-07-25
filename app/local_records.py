"""Per-user local job records and dashboard aggregation."""
import json
import hashlib
import time
import uuid
from collections import Counter
from datetime import datetime


def _now_ms() -> int:
    return int(time.time() * 1000)

from app import database


FIELD_COLUMNS = {
    "公司名称": "company",
    "公司/行业类型": "company_type",
    "嵌入式方向": "directions",
    "进展": "progress",
    "秋招岗位": "job",
    "城市": "city",
    "批次": "batch",
    "优先级": "priority",
    "备注": "note",
    "岗位JD": "job_jd",
    "投递链接": "url",
    "投递截止时间": "deadline",
    "投递时间": "apply_date",
    "机考时间": "exam_date",
    "一面": "interview1",
    "二面": "interview2",
    "三面": "interview3",
    "保温": "warm",
    "结果": "result",
    "Offer总包": "offer_total",
    "Offerbase": "offer_base",
    "Offer奖金": "offer_bonus",
    "Offer决策截止": "offer_deadline",
    "简历版本": "resume_version",
}
JSON_FIELDS = {"嵌入式方向", "进展"}


def _url_value(value) -> str:
    if isinstance(value, dict):
        return str(value.get("link") or value.get("text") or "")
    return str(value or "")


def _db_value(field: str, value):
    if field in JSON_FIELDS:
        if not isinstance(value, list):
            value = [value] if value else []
        return json.dumps(value, ensure_ascii=False)
    if field == "投递链接":
        return _url_value(value)
    return value


def _json_list(value: str | None) -> list:
    try:
        parsed = json.loads(value or "[]")
        return parsed if isinstance(parsed, list) else []
    except (TypeError, json.JSONDecodeError):
        return []


def _row_fields(row: dict) -> dict:
    result = row["result"]
    if isinstance(result, str) and result.isdigit():
        result = int(result)
    return {
        "公司名称": row["company"],
        "公司/行业类型": [row["company_type"]] if row["company_type"] else [],
        "嵌入式方向": _json_list(row["directions"]),
        "进展": _json_list(row["progress"]),
        "秋招岗位": row["job"],
        "城市": row["city"],
        "批次": row["batch"],
        "优先级": row["priority"],
        "备注": row["note"],
        "岗位JD": row["job_jd"],
        "投递链接": row["url"],
        "投递截止时间": row["deadline"],
        "投递时间": row["apply_date"],
        "机考时间": row["exam_date"],
        "一面": row["interview1"],
        "二面": row["interview2"],
        "三面": row["interview3"],
        "保温": row["warm"],
        "结果": result,
        "Offer总包": row["offer_total"] if "offer_total" in row.keys() else "",
        "Offerbase": row["offer_base"] if "offer_base" in row.keys() else "",
        "Offer奖金": row["offer_bonus"] if "offer_bonus" in row.keys() else "",
        "Offer决策截止": row["offer_deadline"] if "offer_deadline" in row.keys() else None,
        "简历版本": row["resume_version"] if "resume_version" in row.keys() else "",
        "progress_updated_at": row["progress_updated_at"] if "progress_updated_at" in row.keys() else None,
    }


def list_records(user_id: int) -> list[dict]:
    db = database.get_db()
    rows = db.execute(
        "SELECT * FROM job_records WHERE user_id = ? ORDER BY created_at DESC, id DESC",
        (user_id,),
    ).fetchall()
    return [{"record_id": row["id"], "fields": _row_fields(dict(row))} for row in rows]


def get_record(user_id: int, record_id: str) -> dict | None:
    db = database.get_db()
    row = db.execute(
        "SELECT * FROM job_records WHERE id = ? AND user_id = ?",
        (record_id, user_id),
    ).fetchone()
    return {"record_id": row["id"], "fields": _row_fields(dict(row))} if row else None


def create_record(user_id: int, fields: dict) -> dict:
    record_id = "rec" + uuid.uuid4().hex
    values = {FIELD_COLUMNS[key]: _db_value(key, value) for key, value in fields.items() if key in FIELD_COLUMNS}
    values["progress_updated_at"] = _now_ms()
    columns = ["id", "user_id", *values.keys()]
    params = [record_id, user_id, *values.values()]
    placeholders = ", ".join("?" for _ in columns)
    with database._write_lock:
        db = database.get_db()
        db.execute(
            f"INSERT INTO job_records ({', '.join(columns)}) VALUES ({placeholders})",
            params,
        )
        db.commit()
    return {"record_id": record_id}


def create_records(user_id: int, records: list[dict]) -> list[str]:
    """Atomically insert several records and return their generated IDs."""
    prepared: list[tuple[list[str], list]] = []
    record_ids: list[str] = []
    for fields in records:
        record_id = "rec" + uuid.uuid4().hex
        values = {
            FIELD_COLUMNS[key]: _db_value(key, value)
            for key, value in fields.items()
            if key in FIELD_COLUMNS
        }
        columns = ["id", "user_id", *values.keys()]
        params = [record_id, user_id, *values.values()]
        prepared.append((columns, params))
        record_ids.append(record_id)

    with database._write_lock:
        db = database.get_db()
        try:
            for columns, params in prepared:
                placeholders = ", ".join("?" for _ in columns)
                db.execute(
                    f"INSERT INTO job_records ({', '.join(columns)}) VALUES ({placeholders})",
                    params,
                )
            db.commit()
        except Exception:
            db.rollback()
            raise
    return record_ids


def _shared_values(fields: dict) -> dict:
    company_types = fields.get("公司/行业类型") or []
    company_type = company_types[0] if isinstance(company_types, list) and company_types else company_types
    directions = list(dict.fromkeys(
        str(item).strip() for item in (fields.get("嵌入式方向") or []) if str(item).strip()
    ))
    return {
        "company": str(fields.get("公司名称") or "").strip(),
        "company_type": str(company_type or "").strip(),
        "directions": directions,
        "job": str(fields.get("秋招岗位") or "").strip(),
        "city": str(fields.get("城市") or "").strip(),
        "batch": str(fields.get("批次") or "秋招").strip() or "秋招",
        "url": _url_value(fields.get("投递链接")).strip(),
        "deadline": fields.get("投递截止时间"),
    }


def shared_missing_fields(fields: dict) -> list[str]:
    values = _shared_values(fields)
    required = [
        ("公司名称", values["company"]),
        ("公司类型", values["company_type"]),
        ("岗位", values["job"]),
        ("方向", values["directions"]),
        ("入口", values["url"]),
    ]
    return [label for label, value in required if not value]


def publish_shared_record(user_id: int, record_id: str) -> tuple[dict, bool]:
    record = get_record(user_id, record_id)
    if not record:
        raise LookupError("未找到对应的个人总表记录")
    fields = record["fields"]
    missing = shared_missing_fields(fields)
    if missing:
        raise ValueError("缺少共享必填项：" + "、".join(missing))
    shared_record, created = create_shared_record(user_id, fields)
    with database._write_lock:
        db = database.get_db()
        db.execute(
            """UPDATE job_records SET source_shared_id = ?, updated_at = datetime('now')
               WHERE id = ? AND user_id = ?""",
            (shared_record["record_id"], record_id, user_id),
        )
        db.commit()
    shared_record["is_added"] = True
    return shared_record, created


def create_shared_record(user_id: int, fields: dict) -> tuple[dict, bool]:
    missing = shared_missing_fields(fields)
    if missing:
        raise ValueError("缺少共享必填项：" + "、".join(missing))
    values = _shared_values(fields)
    canonical = json.dumps({
        "company": values["company"].casefold(),
        "company_type": values["company_type"].casefold(),
        "job": values["job"].casefold(),
        "directions": sorted(item.casefold() for item in values["directions"]),
        "url": values["url"].casefold(),
    }, ensure_ascii=False, sort_keys=True)
    fingerprint = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    shared_id = "shr" + uuid.uuid4().hex
    with database._write_lock:
        db = database.get_db()
        cur = db.execute(
            """INSERT OR IGNORE INTO shared_job_records
               (id, company, company_type, directions, job, city, batch, url,
                deadline, fingerprint, created_by)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                shared_id, values["company"], values["company_type"],
                json.dumps(values["directions"], ensure_ascii=False), values["job"],
                values["city"], values["batch"], values["url"], values["deadline"],
                fingerprint, user_id,
            ),
        )
        created = cur.rowcount > 0
        db.commit()
        row = db.execute(
            """SELECT s.*, u.username AS contributor
               FROM shared_job_records s LEFT JOIN users u ON u.id = s.created_by
               WHERE s.fingerprint = ?""",
            (fingerprint,),
        ).fetchone()
    return _serialize_shared(dict(row), False), created


def create_shared_records(user_id: int, records: list[dict]) -> tuple[int, int]:
    """Validate and insert shared records in one transaction.

    Returns ``(added, skipped)``. The unique fingerprint constraint handles both
    records already in the database and duplicates inside the incoming batch.
    """
    prepared = []
    for fields in records:
        missing = shared_missing_fields(fields)
        if missing:
            raise ValueError("缺少共享必填项：" + "、".join(missing))
        values = _shared_values(fields)
        canonical = json.dumps({
            "company": values["company"].casefold(),
            "company_type": values["company_type"].casefold(),
            "job": values["job"].casefold(),
            "directions": sorted(item.casefold() for item in values["directions"]),
            "url": values["url"].casefold(),
        }, ensure_ascii=False, sort_keys=True)
        prepared.append((
            "shr" + uuid.uuid4().hex,
            values["company"],
            values["company_type"],
            json.dumps(values["directions"], ensure_ascii=False),
            values["job"],
            values["city"],
            values["batch"],
            values["url"],
            values["deadline"],
            hashlib.sha256(canonical.encode("utf-8")).hexdigest(),
            user_id,
        ))
    if not prepared:
        return 0, 0
    with database._write_lock:
        db = database.get_db()
        before = db.total_changes
        try:
            db.executemany(
                """INSERT OR IGNORE INTO shared_job_records
                   (id, company, company_type, directions, job, city, batch, url,
                    deadline, fingerprint, created_by)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                prepared,
            )
            db.commit()
        except Exception:
            db.rollback()
            raise
        added = db.total_changes - before
    return added, len(prepared) - added


def _serialize_shared(row: dict, is_added: bool) -> dict:
    return {
        "record_id": row["id"],
        "company": row["company"],
        "type": row["company_type"],
        "dir": _json_list(row["directions"]),
        "job": row["job"],
        "city": row["city"],
        "batch": row["batch"],
        "url": row["url"],
        "deadline": row["deadline"],
        "priority": "",
        "progress": [],
        "contributor": row.get("contributor") or "已注销用户",
        "created_at": row.get("created_at") or "",
        "is_added": bool(is_added),
    }


def list_shared_records(user_id: int) -> list[dict]:
    db = database.get_db()
    rows = db.execute(
        """SELECT s.*, u.username AS contributor,
                  EXISTS(
                      SELECT 1 FROM job_records j
                      WHERE j.user_id = ? AND (
                          j.source_shared_id = s.id OR
                          (j.company = s.company AND
                           j.company_type = s.company_type AND
                           j.directions = s.directions AND
                           j.job = s.job AND
                           j.url = s.url)
                      )
                  ) AS is_added
           FROM shared_job_records s
           LEFT JOIN users u ON u.id = s.created_by
           ORDER BY s.created_at DESC, s.id DESC""",
        (user_id,),
    ).fetchall()
    return [_serialize_shared(dict(row), bool(row["is_added"])) for row in rows]


def copy_shared_record(user_id: int, shared_id: str) -> tuple[str, bool]:
    with database._write_lock:
        db = database.get_db()
        shared = db.execute(
            "SELECT * FROM shared_job_records WHERE id = ?", (shared_id,)
        ).fetchone()
        if not shared:
            raise LookupError("未找到对应的共享记录")
        existing = db.execute(
            """SELECT id, source_shared_id FROM job_records
               WHERE user_id = ? AND (
                   source_shared_id = ? OR
                   (company = ? AND company_type = ? AND directions = ? AND job = ? AND url = ?)
               ) LIMIT 1""",
            (
                user_id, shared_id, shared["company"], shared["company_type"],
                shared["directions"], shared["job"], shared["url"],
            ),
        ).fetchone()
        if existing:
            if not existing["source_shared_id"]:
                db.execute(
                    "UPDATE job_records SET source_shared_id = ? WHERE id = ?",
                    (shared_id, existing["id"]),
                )
                db.commit()
            return existing["id"], False
        record_id = "rec" + uuid.uuid4().hex
        db.execute(
            """INSERT INTO job_records
               (id, user_id, company, company_type, directions, progress, job,
                city, batch, url, deadline, source_shared_id)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                record_id, user_id, shared["company"], shared["company_type"],
                shared["directions"], json.dumps(["未投递"], ensure_ascii=False),
                shared["job"], shared["city"], shared["batch"], shared["url"],
                shared["deadline"], shared_id,
            ),
        )
        db.commit()
        return record_id, True


def delete_shared_record(shared_id: str) -> bool:
    with database._write_lock:
        db = database.get_db()
        db.execute(
            "UPDATE job_records SET source_shared_id = NULL WHERE source_shared_id = ?",
            (shared_id,),
        )
        cur = db.execute("DELETE FROM shared_job_records WHERE id = ?", (shared_id,))
        db.commit()
        return cur.rowcount > 0


def update_record(user_id: int, record_id: str, fields: dict) -> bool:
    values = {FIELD_COLUMNS[key]: _db_value(key, value) for key, value in fields.items() if key in FIELD_COLUMNS}
    if not values:
        return bool(get_record(user_id, record_id))
    # 进展发生变化时，刷新"进入当前进展的时间"
    if "进展" in fields:
        current = get_record(user_id, record_id)
        old_progress = (current["fields"].get("进展") or []) if current else []
        new_progress = fields.get("进展") or []
        if not isinstance(new_progress, list):
            new_progress = [new_progress] if new_progress else []
        if old_progress != new_progress:
            values["progress_updated_at"] = _now_ms()
    assignments = ", ".join(f"{column} = ?" for column in values)
    with database._write_lock:
        db = database.get_db()
        cur = db.execute(
            f"UPDATE job_records SET {assignments}, updated_at = datetime('now') WHERE id = ? AND user_id = ?",
            [*values.values(), record_id, user_id],
        )
        db.commit()
        return cur.rowcount > 0


def delete_record(user_id: int, record_id: str) -> bool:
    with database._write_lock:
        db = database.get_db()
        cur = db.execute(
            "DELETE FROM job_records WHERE id = ? AND user_id = ?",
            (record_id, user_id),
        )
        db.commit()
        return cur.rowcount > 0


def _serialize(record: dict) -> dict:
    """Serialize a record for list display and detail views."""
    fields = record["fields"]
    return {
        "record_id": record["record_id"],
        "company": fields.get("公司名称", "") or "",
        "type": (fields.get("公司/行业类型") or [""])[0] or "",
        "dir": fields.get("嵌入式方向") or [],
        "progress": fields.get("进展") or [],
        "job": fields.get("秋招岗位") or "",
        "city": fields.get("城市") or "",
        "batch": fields.get("批次") or "",
        "priority": fields.get("优先级") or "",
        "note": fields.get("备注") or "",
        "job_jd": fields.get("岗位JD") or "",
        "url": fields.get("投递链接") or "",
        "deadline": fields.get("投递截止时间"),
        "apply_date": fields.get("投递时间"),
        "exam_date": fields.get("机考时间"),
        "interview1": fields.get("一面"),
        "interview2": fields.get("二面"),
        "interview3": fields.get("三面"),
        "warm": fields.get("保温"),
        "result": fields.get("结果"),
        "offer_total": fields.get("Offer总包") or "",
        "offer_base": fields.get("Offerbase") or "",
        "offer_bonus": fields.get("Offer奖金") or "",
        "offer_deadline": fields.get("Offer决策截止"),
        "resume_version": fields.get("简历版本") or "",
        "progress_updated_at": fields.get("progress_updated_at"),
    }


def get_dashboard_data(user_id: int) -> dict:
    """Single-pass aggregation for better performance."""
    records = list_records(user_id)
    rows = []
    recent = []
    deadlines = []
    progress = Counter()
    directions = Counter()
    company_types = Counter()
    exam_count = 0
    interview_count = 0

    for record in records:
        fields = record["fields"]
        if not fields.get("公司名称"):
            continue
        rows.append(record)

        # Counters
        prog = fields.get("进展") or []
        progress.update(prog)
        directions.update(fields.get("嵌入式方向") or [])
        company_types.update(fields.get("公司/行业类型") or [])

        # Metrics
        if fields.get("机考时间"):
            exam_count += 1
        if fields.get("一面") or fields.get("二面") or fields.get("三面"):
            interview_count += 1

        # Categorize
        if fields.get("投递时间"):
            recent.append(record)
        if fields.get("投递截止时间"):
            deadlines.append(record)

    # Sort only what we need
    recent.sort(key=lambda r: r["fields"].get("投递时间") or 0, reverse=True)
    deadlines.sort(key=lambda r: r["fields"].get("投递截止时间") or 0)

    # Serialize (only once per record)
    return {
        "main": {
            "total_companies": len(recent),
            "exam_count": exam_count,
            "interview_count": interview_count,
            "offer_count": progress.get("OC", 0) + progress.get("Offer", 0),
            "directions": directions.most_common(15),
            "ctypes": company_types.most_common(15),
            "deadlines": [{"company": r["fields"].get("公司名称", ""), "job": r["fields"].get("秋招岗位", ""), "deadline": r["fields"].get("投递截止时间"), "progress": r["fields"].get("进展", [])} for r in deadlines],
            "recent": [_serialize(r) for r in recent],
            "records": [_serialize(r) for r in rows],
        },
        "now": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }
