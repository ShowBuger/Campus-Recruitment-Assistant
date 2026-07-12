"""DeepSeek-powered resume and job analysis."""
import json
import os
from pathlib import Path
from datetime import datetime
from uuid import uuid4

import bleach
import markdown
import requests
from docx import Document
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from pypdf import PdfReader

from app import feishu
from app.routers.resume import RESUME_DIR, _resume_path


router = APIRouter(prefix="/api/ai", tags=["ai"])
PROMPT_PATH = Path(__file__).resolve().parents[1] / "prompts" / "interview_analysis.md"
HISTORY_DIR = Path(__file__).resolve().parents[2] / "analysis_history"
MAX_RESUME_CHARS = 40_000
MARKDOWN_TAGS = {
    "h1", "h2", "h3", "h4", "h5", "h6", "p", "br", "hr",
    "ul", "ol", "li", "strong", "em", "blockquote", "code", "pre",
    "table", "thead", "tbody", "tr", "th", "td", "a",
}


class AnalysisRequest(BaseModel):
    resume_filename: str
    record_id: str


def _render_markdown(content: str) -> str:
    rendered = markdown.markdown(content, extensions=["fenced_code", "tables", "sane_lists"])
    return bleach.clean(
        rendered,
        tags=MARKDOWN_TAGS,
        attributes={"a": ["href", "title"]},
        protocols={"http", "https", "mailto"},
        strip=True,
    )


def _save_history(data: dict) -> str:
    HISTORY_DIR.mkdir(parents=True, exist_ok=True)
    history_id = datetime.now().strftime("%Y%m%d-%H%M%S") + "-" + uuid4().hex[:8]
    target = HISTORY_DIR / f"{history_id}.json"
    temp = target.with_suffix(".json.tmp")
    payload = {"id": history_id, "created_at": datetime.now().isoformat(timespec="seconds"), **data}
    temp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(temp, target)
    return history_id


def _history_path(history_id: str) -> Path:
    if not history_id or any(ch not in "0123456789abcdefghijklmnopqrstuvwxyz-" for ch in history_id.lower()):
        raise HTTPException(status_code=400, detail="无效的分析记录 ID")
    return HISTORY_DIR / f"{history_id}.json"


@router.get("/history")
def list_history():
    HISTORY_DIR.mkdir(parents=True, exist_ok=True)
    items = []
    for path in sorted(HISTORY_DIR.glob("*.json"), reverse=True):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            items.append({key: data.get(key, "") for key in ("id", "created_at", "company", "job", "resume", "model")})
        except (OSError, ValueError):
            continue
    return {"items": items}


@router.get("/history/{history_id}")
def get_history(history_id: str):
    path = _history_path(history_id)
    if not path.is_file():
        raise HTTPException(status_code=404, detail="分析记录不存在")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise HTTPException(status_code=422, detail="分析记录文件损坏") from exc
    analysis = str(data.get("analysis") or "")
    return {**data, "analysis_html": _render_markdown(analysis)}


def _extract_resume_text(path: Path) -> str:
    if path.suffix.lower() == ".pdf":
        reader = PdfReader(path)
        text = "\n".join(page.extract_text() or "" for page in reader.pages)
    else:
        document = Document(path)
        parts = [paragraph.text for paragraph in document.paragraphs if paragraph.text.strip()]
        for table in document.tables:
            for row in table.rows:
                parts.append(" | ".join(cell.text.strip() for cell in row.cells))
        text = "\n".join(parts)
    text = text.strip()
    if not text:
        raise HTTPException(status_code=422, detail="简历未提取到文本，扫描版 PDF 请先进行 OCR")
    return text[:MAX_RESUME_CHARS]


def _find_record(record_id: str) -> dict:
    if not record_id.startswith("rec"):
        raise HTTPException(status_code=422, detail="无效的飞书记录 ID")
    record = next(
        (item for item in feishu.list_records(feishu.MAIN_TABLE_ID) if item.get("record_id") == record_id),
        None,
    )
    if not record:
        raise HTTPException(status_code=404, detail="未找到所选总表记录")
    return record.get("fields") or {}


@router.post("/analyze")
def analyze_resume(request: AnalysisRequest):
    resume_path = _resume_path(request.resume_filename)
    if not resume_path.is_file() or resume_path.parent != RESUME_DIR:
        raise HTTPException(status_code=404, detail="所选简历不存在")
    api_key = (feishu.DEEPSEEK_API_KEY or "").strip()
    if not api_key:
        raise HTTPException(status_code=400, detail="请先在飞书配置中填写 DeepSeek API Key")

    fields = _find_record(request.record_id)
    resume_text = _extract_resume_text(resume_path)
    system_prompt = PROMPT_PATH.read_text(encoding="utf-8")
    company = str(fields.get("公司名称") or "")
    job = str(fields.get("秋招岗位") or "")
    job_jd = str(fields.get("岗位JD") or "")
    if not job_jd.strip():
        raise HTTPException(status_code=422, detail="所选记录尚未填写岗位 JD")

    user_content = f"""请分析以下岗位与简历：

【公司名称】
{company}

【岗位名称】
{job}

【岗位 JD】
{job_jd}

【候选人简历】
{resume_text}
"""
    try:
        response = requests.post(
            "https://api.deepseek.com/chat/completions",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={
                "model": feishu.DEEPSEEK_MODEL or "deepseek-v4-flash",
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_content},
                ],
                "stream": False,
            },
            timeout=180,
        )
        if not response.ok:
            try:
                detail = response.json().get("error", {}).get("message") or response.text
            except Exception:
                detail = response.text
            raise HTTPException(status_code=502, detail=f"DeepSeek API 请求失败：{detail[:500]}")
        payload = response.json()
        content = payload["choices"][0]["message"]["content"]
    except HTTPException:
        raise
    except requests.RequestException as exc:
        raise HTTPException(status_code=502, detail=f"无法连接 DeepSeek API：{exc}") from exc
    except (KeyError, IndexError, TypeError, ValueError) as exc:
        raise HTTPException(status_code=502, detail="DeepSeek API 返回格式异常") from exc

    safe_html = _render_markdown(content)
    history_id = _save_history({
        "company": company,
        "job": job,
        "resume": resume_path.name,
        "model": feishu.DEEPSEEK_MODEL or "deepseek-v4-flash",
        "record_id": request.record_id,
        "analysis": content,
    })
    return {
        "success": True,
        "analysis": content,
        "analysis_html": safe_html,
        "model": feishu.DEEPSEEK_MODEL or "deepseek-v4-flash",
        "company": company,
        "job": job,
        "resume": resume_path.name,
        "history_id": history_id,
    }
