"""DeepSeek-powered resume and job analysis — per-user isolation."""
import json
import os
import re
from pathlib import Path
from datetime import datetime
from uuid import uuid4
from urllib.parse import quote

import bleach
import markdown
import requests
from docx import Document
from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, Field
from pypdf import PdfReader

from app import auth as auth_module, database, feishu


router = APIRouter(prefix="/api/ai", tags=["ai"])
PROMPT_PATH = Path(__file__).resolve().parents[1] / "prompts" / "interview_analysis.md"
PROJECT_DIR = Path(__file__).resolve().parents[2]
MAX_RESUME_CHARS = 40_000
MARKDOWN_TAGS = {
    "h1", "h2", "h3", "h4", "h5", "h6", "p", "br", "hr",
    "ul", "ol", "li", "strong", "em", "blockquote", "code", "pre",
    "table", "thead", "tbody", "tr", "th", "td", "a",
}


class AnalysisRequest(BaseModel):
    resume_filename: str
    record_id: str
    analysis_mode: str = "match"
    focus: str = Field(default="", max_length=1000)


ANALYSIS_MODES = {
    "match": {
        "label": "综合匹配分析",
        "instruction": """请输出：
# 匹配结论
- 综合匹配度（0-100 分）、一句话判断、最适合强调的候选人定位
## JD 核心要求
## 简历匹配优势
列出 3-5 条，每条引用具体证据。
## 缺口与风险
列出 3-5 条并标注“未体现/证据不足/可能缺乏”。
## 简历修改建议
## 面试重点
## 针对性面试题
生成 8 道题，每题包含考察点、回答思路和可能追问。
## 7 天准备计划""",
    },
    "technical": {
        "label": "技术面试训练",
        "instruction": """生成 10 道针对性技术面试题：技术基础 3-4 道、项目深挖 3-4 道、系统/场景题 1-2 道、反问环节 1 道。
每题严格包含：题目类型、题目、依据（JD 或简历）、难度、参考回答框架、优秀回答应包含的证据、可能追问。
最后输出“最高风险知识点”和“面试前冲刺清单”。""",
    },
    "hr": {
        "label": "HR 面试训练",
        "instruction": """生成 8 道校招 HR 面专项问题，覆盖求职动机、公司与岗位理解、地点接受度、offer 选择、稳定性、协作冲突、职业规划和薪资预期。
每题包含：HR 真正判断什么、结合本简历的回答原则、可直接说出口的回答框架、踩坑提醒、可能追问。
最后总结候选人的 HR 面风险与应对策略。""",
    },
    "full": {
        "label": "完整面试流程",
        "instruction": """设计一套连贯的完整面试流程：
# 整体判断
## Round 1 · 一面
基础知识与简历入口，至少 5 题。
## Round 2 · 二面
项目深挖、技术方案和权衡，至少 5 题，并承接一面暴露的问题。
## Round 3 · 三面
综合判断、协作、业务理解和成长潜力，至少 4 题。
## Round 4 · HR 面
动机、稳定性、地点、薪资和规划，至少 5 题。
每轮说明关注点、通过关键、淘汰风险和准备建议。""",
    },
    "resume": {
        "label": "简历定向优化",
        "instruction": """针对目标岗位审查简历并输出：
# 简历诊断摘要
## 应保留和强化的内容
## 应删除或弱化的内容
## 缺失的关键词与证据
## 逐段修改建议
引用原表述，给出修改方向和示例表达；禁止虚构数据。
## 项目经历重写模板
## 面向该岗位的一分钟自我介绍
## 修改优先级清单
按 P0/P1/P2 排序。""",
    },
}


def _render_markdown(content: str) -> str:
    rendered = markdown.markdown(content, extensions=["fenced_code", "tables", "sane_lists"])
    return bleach.clean(
        rendered,
        tags=MARKDOWN_TAGS,
        attributes={"a": ["href", "title"]},
        protocols={"http", "https", "mailto"},
        strip=True,
    )


def _user_history_dir(user_id: int) -> Path:
    d = PROJECT_DIR / "data" / "users" / str(user_id) / "analysis_history"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _save_history(data: dict, user_id: int) -> str:
    hist_dir = _user_history_dir(user_id)
    history_id = datetime.now().strftime("%Y%m%d-%H%M%S") + "-" + uuid4().hex[:8]
    target = hist_dir / f"{history_id}.json"
    temp = target.with_suffix(".json.tmp")
    payload = {"id": history_id, "created_at": datetime.now().isoformat(timespec="seconds"), **data}
    temp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(temp, target)
    return history_id


def _history_path(history_id: str, user_id: int) -> Path:
    if not history_id or any(ch not in "0123456789abcdefghijklmnopqrstuvwxyz-" for ch in history_id.lower()):
        raise HTTPException(status_code=400, detail="无效的分析记录 ID")
    return _user_history_dir(user_id) / f"{history_id}.json"


def _user_resume_path(user_id: int, filename: str) -> Path:
    clean = Path(filename).name
    from app.routers.resume import ALLOWED_SUFFIXES
    if not clean or Path(clean).suffix.lower() not in ALLOWED_SUFFIXES:
        raise HTTPException(status_code=400, detail="无效的简历文件名")
    return PROJECT_DIR / "data" / "users" / str(user_id) / "resumes" / clean


@router.get("/history")
def list_history(user: dict = Depends(auth_module.get_current_user)):
    hist_dir = _user_history_dir(user["user_id"])
    items = []
    for path in sorted(hist_dir.glob("*.json"), reverse=True):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            items.append({
                key: data.get(key, "")
                for key in (
                    "id", "created_at", "company", "job", "resume", "model",
                    "analysis_mode", "analysis_mode_label",
                )
            })
        except (OSError, ValueError):
            continue
    return {"items": items}


@router.get("/history/{history_id}")
def get_history(history_id: str, user: dict = Depends(auth_module.get_current_user)):
    path = _history_path(history_id, user["user_id"])
    if not path.is_file():
        raise HTTPException(status_code=404, detail="分析记录不存在")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise HTTPException(status_code=422, detail="分析记录文件损坏") from exc
    analysis = str(data.get("analysis") or "")
    return {**data, "analysis_html": _render_markdown(analysis)}


@router.get("/history/{history_id}/download")
def download_history(history_id: str, user: dict = Depends(auth_module.get_current_user)):
    path = _history_path(history_id, user["user_id"])
    if not path.is_file():
        raise HTTPException(status_code=404, detail="分析记录不存在")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise HTTPException(status_code=422, detail="分析记录文件损坏") from exc
    analysis = str(data.get("analysis") or "")
    company = re.sub(r'[\\/:*?"<>|]+', "_", str(data.get("company") or "公司"))
    job = re.sub(r'[\\/:*?"<>|]+', "_", str(data.get("job") or "岗位"))
    created = str(data.get("created_at") or history_id).replace(":", "-").replace("T", "_")
    filename = f"{company}-{job}-{created}.md"
    return Response(
        content=analysis.encode("utf-8"),
        media_type="text/markdown; charset=utf-8",
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(filename)}"},
    )


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


def _find_record(record_id: str, user_id: int) -> dict:
    if not record_id.startswith("rec"):
        raise HTTPException(status_code=422, detail="无效的飞书记录 ID")
    cfg = database.get_user_config(user_id)
    table_id = cfg.get("main_table_id", "")
    if not table_id:
        raise HTTPException(status_code=400, detail="请先在飞书配置中填写表格信息")
    feishu.set_request_config({
        "APP_ID": cfg.get("feishu_app_id", ""),
        "APP_SECRET": cfg.get("feishu_app_secret", ""),
        "APP_TOKEN": cfg.get("feishu_app_token", ""),
        "MAIN_TABLE_ID": table_id,
        "DEEPSEEK_API_KEY": cfg.get("deepseek_api_key", ""),
        "DEEPSEEK_MODEL": cfg.get("deepseek_model", "deepseek-v4-flash"),
    })
    record = next(
        (item for item in feishu.list_records(table_id) if item.get("record_id") == record_id),
        None,
    )
    if not record:
        raise HTTPException(status_code=404, detail="未找到所选总表记录")
    return record.get("fields") or {}


@router.post("/analyze")
def analyze_resume(
    request: AnalysisRequest,
    user: dict = Depends(auth_module.get_current_user),
):
    cfg = database.get_user_config(user["user_id"])
    api_key = cfg.get("deepseek_api_key", "")
    if not api_key:
        raise HTTPException(status_code=400, detail="请先在飞书配置中填写 DeepSeek API Key")
    model = cfg.get("deepseek_model", "") or "deepseek-v4-flash"

    resume_path = _user_resume_path(user["user_id"], request.resume_filename)
    if not resume_path.is_file():
        raise HTTPException(status_code=404, detail="所选简历不存在")
    mode = ANALYSIS_MODES.get(request.analysis_mode)
    if not mode:
        raise HTTPException(status_code=422, detail="不支持的分析模式")

    fields = _find_record(request.record_id, user["user_id"])
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

【本次任务】
{mode['label']}

【输出要求】
{mode['instruction']}

【用户特别关注】
{request.focus.strip() or '无，请按默认流程全面分析。'}
"""
    try:
        response = requests.post(
            "https://api.deepseek.com/chat/completions",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={
                "model": model,
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
        "model": model,
        "analysis_mode": request.analysis_mode,
        "analysis_mode_label": mode["label"],
        "record_id": request.record_id,
        "analysis": content,
    }, user["user_id"])
    return {
        "success": True,
        "analysis": content,
        "analysis_html": safe_html,
        "model": model,
        "company": company,
        "job": job,
        "resume": resume_path.name,
        "history_id": history_id,
        "analysis_mode": request.analysis_mode,
        "analysis_mode_label": mode["label"],
    }
