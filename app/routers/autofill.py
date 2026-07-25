"""Auto-fill plugin: resume profiles, page proxy, field detection, AI matching — per-user isolation."""
import html as html_mod
import json
import os
import re
import time
import io
import zipfile
import secrets
import threading
from pathlib import Path
from datetime import datetime
from urllib.parse import urljoin, urlparse, quote, unquote

import requests
from bs4 import BeautifulSoup
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, Response
from pydantic import BaseModel, Field

from app import auth as auth_module, database
from app.ai_provider_utils import validate_public_base_url, endpoint_url, auth_headers, DEFAULT_BASE_URLS

router = APIRouter(prefix="/api/autofill", tags=["autofill"])
PROJECT_DIR = Path(__file__).resolve().parents[2]

# ── Resume profiles ──────────────────────────────────────────────

PROFILE_FIELDS = [
    "姓名", "邮箱", "手机", "性别", "出生日期", "民族", "政治面貌",
    "学校", "专业", "学历", "毕业时间", "英语水平",
    "实习经历", "项目经历", "技能", "获奖情况", "自我评价",
    "期望城市", "期望薪资", "最快到岗", "GitHub", "博客",
]


def _profiles_path(user_id: int) -> Path:
    d = PROJECT_DIR / "data" / "users" / str(user_id) / "autofill_profiles"
    d.mkdir(parents=True, exist_ok=True)
    p = d / "profiles.json"
    if not p.exists():
        p.write_text("{}", encoding="utf-8")
    return p


def _load_profiles(user_id: int) -> dict:
    try:
        return json.loads(_profiles_path(user_id).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _save_profiles(user_id: int, data: dict) -> None:
    tmp = _profiles_path(user_id).with_suffix(".json.tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, _profiles_path(user_id))


@router.get("/profiles")
def list_profiles(user: dict = Depends(auth_module.get_current_user)):
    profiles = _load_profiles(user["user_id"])
    return {
        "profiles": [
            {"id": pid, "name": p.get("name", pid), "field_count": len(p.get("fields", {}))}
            for pid, p in profiles.items()
        ]
    }


@router.get("/profiles/{profile_id}")
def get_profile(profile_id: str, user: dict = Depends(auth_module.get_current_user)):
    profiles = _load_profiles(user["user_id"])
    if profile_id not in profiles:
        raise HTTPException(status_code=404, detail="简历模板不存在")
    return {"id": profile_id, **profiles[profile_id]}


class ProfileSave(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    fields: dict = Field(default_factory=dict)


@router.post("/profiles")
def create_profile(body: ProfileSave, user: dict = Depends(auth_module.get_current_user)):
    profiles = _load_profiles(user["user_id"])
    pid = datetime.now().strftime("%Y%m%d%H%M%S") + "-" + os.urandom(4).hex()
    profiles[pid] = {"name": body.name.strip(), "fields": body.fields}
    _save_profiles(user["user_id"], profiles)
    return {"success": True, "message": "模板已创建", "id": pid}


@router.put("/profiles/{profile_id}")
def update_profile(profile_id: str, body: ProfileSave, user: dict = Depends(auth_module.get_current_user)):
    profiles = _load_profiles(user["user_id"])
    if profile_id not in profiles:
        raise HTTPException(status_code=404, detail="简历模板不存在")
    profiles[profile_id] = {"name": body.name.strip(), "fields": body.fields}
    _save_profiles(user["user_id"], profiles)
    return {"success": True, "message": "模板已更新"}


@router.delete("/profiles/{profile_id}")
def delete_profile(profile_id: str, user: dict = Depends(auth_module.get_current_user)):
    profiles = _load_profiles(user["user_id"])
    if profile_id not in profiles:
        raise HTTPException(status_code=404, detail="简历模板不存在")
    del profiles[profile_id]
    _save_profiles(user["user_id"], profiles)
    return {"success": True, "message": "模板已删除"}


# ── Field name mapping table ─────────────────────────────────────

FIELD_ALIASES = {
    "姓名": ["name", "姓名", "fullname", "your-name", "username", "realname", "真实姓名", "中文姓名",
             "firstname", "first_name", "lastname", "last_name", "familyname",
             "candidate_name", "applicant_name"],
    "邮箱": ["email", "邮箱", "电子邮箱", "e-mail", "mail", "email_address", "联系邮箱",
             "emailaddress", "e_mail"],
    "手机": ["phone", "手机", "电话", "mobile", "tel", "telephone", "联系电话", "手机号码",
             "cellphone", "cell_phone", "phonenumber", "phone_number", "contact_number",
             "mobilephone", "mobile_phone"],
    "性别": ["gender", "sex", "性别", "male", "female"],
    "出生日期": ["birthday", "birth", "出生日期", "出生年月", "birthdate", "date_of_birth",
                 "birth_date", "dob"],
    "民族": ["ethnicity", "nation", "民族", "ethnic", "nationality"],
    "政治面貌": ["political", "政治面貌", "政治背景", "politics", "political_status",
                 "party", "党派", "团员", "党员"],
    "学校": ["school", "学校", "毕业学校", "毕业院校", "university", "college", "院校",
             "institution", "education_school", "school_name"],
    "专业": ["major", "专业", "specialty", "speciality", "discipline", "所学专业",
             "major_name", "subject"],
    "学历": ["education", "degree", "学历", "最高学历", "edu", "education_level",
             "qualification", "academic_degree", "highest_degree"],
    "毕业时间": ["graduation", "毕业时间", "graduation_date", "graduate_date",
                 "graduation_year", "预计毕业", "expected_graduation", "graduate_time"],
    "英语水平": ["english", "英语水平", "英语等级", "english_level", "cet", "toefl",
                 "ielts", "外语水平", "language", "language_skill", "english_proficiency"],
    "实习经历": ["internship", "实习经历", "实习", "intern", "intern_experience",
                 "work_experience", "工作经历", "experience"],
    "项目经历": ["project", "项目经历", "项目经验", "project_experience", "projects"],
    "技能": ["skills", "skill", "技能", "专业技能", "技术栈", "tech_skills",
             "technical_skills", "core_skills", "technologies"],
    "获奖情况": ["awards", "award", "获奖", "获奖情况", "荣誉", "honors", "奖励",
                 "achievements", "scholarship", "奖学金"],
    "自我评价": ["self_evaluation", "self_intro", "self_introduction", "自我评价",
                 "自我介绍", "个人简介", "个人介绍", "summary", "bio", "biography",
                 "personal_summary", "about_me", "introduction"],
    "期望城市": ["city", "城市", "期望城市", "工作城市", "location", "preferred_city",
                 "work_city", "意向城市", "期望工作地"],
    "期望薪资": ["salary", "薪资", "期望薪资", "expected_salary", "salary_expectation",
                 "salary_range", "薪酬", "薪资要求"],
    "最快到岗": ["availability", "到岗时间", "最快到岗", "入职时间", "available_date",
                 "start_date", "onboard_date", "available_from", "到岗日期"],
    "GitHub": ["github", "gitlab", "gitee", "代码仓库", "个人主页", "portfolio",
               "website", "personal_website", "博客", "blog", "个人网站", "主页"],
    "博客": ["blog", "博客", "blog_url", "技术博客", "csdn", "掘金", "知乎",
             "简书", "segmentfault"],
}


def _score_field_match(label_text: str, input_name: str, input_id: str, placeholder: str) -> dict:
    """Return best-matching profile field key and confidence score (0-100)."""
    best_field = None
    best_score = 0
    haystack = f"{label_text} {input_name} {input_id} {placeholder}".lower()
    haystack_clean = re.sub(r"[_\-\s]+", "", haystack)

    for profile_key, aliases in FIELD_ALIASES.items():
        for alias in aliases:
            alias_clean = re.sub(r"[_\-\s]+", "", alias.lower())
            if alias.lower() in haystack or alias_clean in haystack_clean:
                score = 95 if alias.lower() in label_text.lower() else \
                        85 if alias.lower() == input_name.lower() else \
                        75 if alias.lower() in (input_id or "").lower() else \
                        65 if alias.lower() in (placeholder or "").lower() else 55
                if score > best_score:
                    best_score = score
                    best_field = profile_key
        if best_score >= 85:
            break
    return {"field": best_field, "score": best_score}


# ── Field detection ──────────────────────────────────────────────

class DetectRequest(BaseModel):
    html: str = Field(max_length=500_000)
    url: str = ""


@router.post("/detect-fields")
def detect_fields(body: DetectRequest, user: dict = Depends(auth_module.get_current_user)):
    """Analyze HTML and return detected form fields with suggested mappings."""
    soup = BeautifulSoup(body.html, "lxml")
    if not soup:
        raise HTTPException(status_code=422, detail="无法解析页面 HTML")

    detected = []
    seen = set()

    for tag in soup.find_all(["input", "textarea", "select"]):
        if not tag.get("name") and not tag.get("id"):
            continue

        tag_type = tag.get("type", "text") if tag.name == "input" else tag.name
        if tag_type in ("hidden", "submit", "button", "reset", "image", "file"):
            continue

        name = (tag.get("name") or "").strip()
        uid = (tag.get("id") or "").strip()
        placeholder = (tag.get("placeholder") or "").strip()
        required = tag.get("required") is not None or tag.get("aria-required") == "true"

        # Find associated label
        label_text = ""
        label = tag.find_previous("label")
        if not label:
            if uid:
                label = soup.find("label", attrs={"for": uid})
        if label:
            label_text = label.get_text(" ", strip=True)
        if not label_text and name:
            # Look for label by proximity
            prev = tag.find_previous_sibling()
            if prev and prev.name == "label":
                label_text = prev.get_text(" ", strip=True)

        dedup_key = f"{name}|{uid}|{label_text}"
        if dedup_key in seen:
            continue
        seen.add(dedup_key)

        match = _score_field_match(label_text, name, uid, placeholder)

        # Collect options for select
        options = []
        if tag.name == "select":
            for opt in tag.find_all("option"):
                val = (opt.get("value") or "").strip()
                txt = opt.get_text(" ", strip=True)
                if val or txt:
                    options.append({"value": val, "text": txt})

        detected.append({
            "name": name,
            "id": uid,
            "type": tag_type,
            "label": label_text,
            "placeholder": placeholder,
            "required": required,
            "suggested_field": match["field"],
            "confidence": match["score"],
            "options": options[:50],
        })

    return {
        "fields": detected,
        "count": len(detected),
        "mapped_count": sum(1 for d in detected if d["suggested_field"]),
    }


# ── Normalize value for a detected HTML field ─────────────────────

def _normalize_field_value(profile_field: str, value: str, field_info: dict) -> str:
    """Adjust profile value to fit the detected HTML field type."""
    tag_type = field_info.get("type", "text")
    label = (field_info.get("label") or "").lower()
    options = field_info.get("options") or []

    if tag_type == "select" or options:
        # Try fuzzy match against options
        val_lower = value.strip().lower()
        for opt in options:
            opt_text = opt.get("text", "").strip()
            opt_val = opt.get("value", "").strip()
            if val_lower == opt_text.lower() or val_lower == opt_val.lower():
                return opt_val or opt_text
        # Partial match
        for opt in options:
            opt_text = opt.get("text", "").strip()
            if val_lower in opt_text.lower() or opt_text.lower() in val_lower:
                return opt.get("value") or opt_text
        return ""

    if tag_type == "date":
        # Try to extract date from profile value
        match = re.search(r"(\d{4})[年\-/](\d{1,2})[月\-/]?", value)
        if match:
            return f"{match.group(1)}-{int(match.group(2)):02d}"
        return value

    if tag_type in ("number", "tel", "email", "url"):
        return value.strip()

    # For gender fields with radio-like behavior
    if "性别" in label or "gender" in label:
        v = value.strip()
        if v in ("男", "male", "Male", "M"):
            return v
        if v in ("女", "female", "Female", "F"):
            return v

    return value.strip()


# ── In-memory page cache (TTL: 10 minutes) ──────────────────────

_view_cache: dict = {}        # token -> {"html": ..., "base_url": ..., "title": ..., "expires_at": float}
_view_cache_lock = threading.Lock()
_VIEW_CACHE_TTL = 600          # 10 minutes


def _cache_cleanup():
    """Remove expired entries."""
    now = time.time()
    with _view_cache_lock:
        expired = [t for t, v in _view_cache.items() if v["expires_at"] < now]
        for t in expired:
            del _view_cache[t]


def _cache_put(html: str, base_url: str, title: str) -> str:
    _cache_cleanup()
    token = secrets.token_urlsafe(16)
    with _view_cache_lock:
        _view_cache[token] = {
            "html": html,
            "base_url": base_url,
            "title": title,
            "expires_at": time.time() + _VIEW_CACHE_TTL,
        }
    return token


def _cache_get(token: str) -> dict | None:
    _cache_cleanup()
    with _view_cache_lock:
        entry = _view_cache.get(token)
        if entry and entry["expires_at"] >= time.time():
            return entry
        if entry:
            del _view_cache[token]
    return None

FILL_BRIDGE_JS = r"""
(function() {
  if (window.__autofillBridge) return;
  window.__autofillBridge = true;

  function collectFields() {
    var fields = [];
    var seen = {};
    var inputs = document.querySelectorAll('input:not([type="hidden"]):not([type="submit"]):not([type="button"]):not([type="reset"]):not([type="image"]):not([type="file"]), textarea, select');
    inputs.forEach(function(el) {
      var name = (el.name || '').trim();
      var id = (el.id || '').trim();
      var label = '';
      var lbl = document.querySelector('label[for="' + CSS.escape(id) + '"]');
      if (!lbl && el.closest) {
        var row = el.closest('label') || el.closest('.form-item') || el.closest('.form-group') || el.closest('tr') || el.closest('div');
        if (row) lbl = row.querySelector('label');
      }
      if (lbl) label = (lbl.textContent || '').replace(/\s+/g, ' ').trim();
      var key = name + '|' + id + '|' + label;
      if (seen[key]) return; seen[key] = true;

      var options = [];
      if (el.tagName === 'SELECT') {
        Array.from(el.options).forEach(function(o) {
          options.push({value: o.value || '', text: (o.textContent || '').trim()});
        });
      }

      fields.push({
        name: name, id: id,
        type: el.type || el.tagName.toLowerCase(),
        label: label,
        placeholder: (el.placeholder || '').trim(),
        required: el.required || el.getAttribute('aria-required') === 'true',
        options: options.slice(0, 50),
        tagName: el.tagName
      });
    });
    return fields;
  }

  function fillField(fieldInfo, value) {
    if (!value) return false;
    var el = null;
    if (fieldInfo.id) el = document.getElementById(fieldInfo.id);
    if (!el && fieldInfo.name) el = document.querySelector('[name="' + CSS.escape(fieldInfo.name) + '"]');
    if (!el) return false;
    try {
      if (el.tagName === 'SELECT') {
        var opts = el.options;
        for (var i = 0; i < opts.length; i++) {
          if (opts[i].textContent.trim().toLowerCase() === value.toLowerCase() ||
              opts[i].value.toLowerCase() === value.toLowerCase() ||
              opts[i].textContent.trim().toLowerCase().indexOf(value.toLowerCase()) >= 0) {
            el.value = opts[i].value;
            el.dispatchEvent(new Event('change', {bubbles: true}));
            return true;
          }
        }
        return false;
      }
      var nativeSetter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value') ||
                         Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype, 'value');
      if (nativeSetter && nativeSetter.set) {
        nativeSetter.set.call(el, value);
      } else {
        el.value = value;
      }
      el.dispatchEvent(new Event('input', {bubbles: true}));
      el.dispatchEvent(new Event('change', {bubbles: true}));
      return true;
    } catch(e) {
      try { el.value = value; el.dispatchEvent(new Event('change', {bubbles: true})); return true; }
      catch(e2) { return false; }
    }
  }

  window.addEventListener('message', function(event) {
    var data = event.data;
    if (!data || data.source !== 'autofill') return;
    switch(data.action) {
      case 'collect':
        event.source.postMessage({
          source: 'autofill-bridge', action: 'fields',
          fields: collectFields(), url: location.href, title: document.title
        }, '*');
        break;
      case 'fill':
        var results = (data.fields || []).map(function(item) {
          return {field: item.field, filled: fillField(item.field, item.value)};
        });
        event.source.postMessage({
          source: 'autofill-bridge', action: 'fill-result',
          results: results, total: results.length,
          succeeded: results.filter(function(r) { return r.filled; }).length
        }, '*');
        break;
      case 'fill-one':
        var ok = fillField(data.fieldInfo, data.value);
        event.source.postMessage({
          source: 'autofill-bridge', action: 'fill-one-result',
          field: data.field, filled: ok
        }, '*');
        break;
    }
  });

  var observer = new MutationObserver(function(mutations) {
    var added = false;
    mutations.forEach(function(m) {
      m.addedNodes.forEach(function(node) {
        if (node.nodeType === 1 && (node.querySelectorAll || node.matches)) {
          if (node.matches && (node.matches('input,textarea,select') ||
              node.querySelectorAll('input,textarea,select').length)) {
            added = true;
          }
        }
      });
    });
    if (added) {
      window.parent.postMessage({source: 'autofill-bridge', action: 'dom-changed'}, '*');
    }
  });
  observer.observe(document.documentElement, {childList: true, subtree: true});
})();
"""

# Helper: rewrite resource URLs to absolute for iframe loading
_SRC_ATTRS = [
    ("script", "src"), ("link", "href"), ("img", "src"),
    ("a", "href"), ("form", "action"), ("source", "src"),
    ("iframe", "src"), ("video", "src"), ("audio", "src"),
    ("embed", "src"), ("object", "data"), ("use", "href"),
]


def _abs_url(raw: str, base: str) -> str:
    """Resolve a potentially relative URL to absolute using base."""
    if not raw or raw.startswith("data:") or raw.startswith("#") or raw.startswith("javascript:"):
        return raw
    return urljoin(base, raw)


def _fix_encoding(resp: requests.Response) -> str:
    """Detect and return properly decoded HTML text."""
    if resp.apparent_encoding and resp.apparent_encoding != "ascii":
        resp.encoding = resp.apparent_encoding
    elif not resp.encoding or resp.encoding.upper() in ("ISO-8859-1", "LATIN-1"):
        # Try to detect from HTML meta
        meta = re.search(rb'charset[="\'\s]+([^"\'\s;>]+)', resp.content[:2000], re.IGNORECASE)
        if meta:
            try:
                resp.encoding = meta.group(1).decode("ascii")
            except Exception:
                resp.encoding = "utf-8"
        else:
            resp.encoding = "utf-8"
    return resp.text


def _rewrite_html(html_content: str, base_url: str, proxy_base: str) -> str:
    """Rewrite relative URLs to absolute, inject bridge, return processed HTML."""
    soup = BeautifulSoup(html_content, "lxml")
    if not soup:
        return html_content

    # Add base tag
    head = soup.find("head")
    if not head:
        head = soup.new_tag("head")
        if soup.html:
            soup.html.insert(0, head)
        else:
            soup.insert(0, head)
    base_tag = soup.new_tag("base", href=base_url)
    head.insert(0, base_tag)

    # Rewrite all src/href/action attributes to absolute
    for tag_name, attr in _SRC_ATTRS:
        for tag in soup.find_all(tag_name):
            val = tag.get(attr)
            if val:
                tag[attr] = _abs_url(val, base_url)

    # Also rewrite url() in inline styles
    for tag in soup.find_all(style=True):
        style = tag["style"]
        if "url(" in style:
            def _replace_url(m):
                u = m.group(1).strip("\"'")
                return f"url({_abs_url(u, base_url)})"
            tag["style"] = re.sub(r"url\(([^)]+)\)", _replace_url, style)

    # Inject bridge script before </body>
    bridge_tag = soup.new_tag("script")
    bridge_tag.string = FILL_BRIDGE_JS
    body = soup.find("body")
    if body:
        body.append(bridge_tag)
    else:
        if soup.html:
            soup.html.append(bridge_tag)
        else:
            soup.append(bridge_tag)

    return str(soup)


class ProxyRequest(BaseModel):
    url: str = Field(min_length=5, max_length=2000)
    record_id: str = ""


@router.post("/proxy")
def proxy_page(body: ProxyRequest, user: dict = Depends(auth_module.get_current_user)):
    """Fetch external page, process it, return a view token for the GET endpoint."""
    target_url = body.url.strip()
    parsed = urlparse(target_url)
    if parsed.scheme not in ("http", "https"):
        raise HTTPException(status_code=400, detail="仅支持 http/https 链接")

    try:
        import ipaddress, socket
        hostname = parsed.hostname or ""
        ip = socket.gethostbyname(hostname)
        addr = ipaddress.ip_address(ip)
        if addr.is_private or addr.is_loopback or addr.is_link_local:
            raise HTTPException(status_code=400, detail="不允许代理内网地址")
    except HTTPException:
        raise
    except Exception:
        pass

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    }
    try:
        resp = requests.get(target_url, headers=headers, timeout=30, allow_redirects=True)
    except requests.RequestException as exc:
        raise HTTPException(status_code=502, detail=f"无法访问目标页面：{exc}")

    content_type = resp.headers.get("Content-Type", "")
    if "text/html" not in content_type and not target_url.endswith((".htm", ".html")):
        raise HTTPException(status_code=415, detail="目标页面不是 HTML 格式")

    html_content = _fix_encoding(resp)
    if not html_content.strip():
        raise HTTPException(status_code=502, detail="目标页面返回空内容")

    base_url = resp.url or target_url

    # Build proxy base URL for resource rewriting
    proxy_base = f"/api/autofill/view?url={quote(target_url, safe='')}&token="

    # Process HTML
    processed = _rewrite_html(html_content, base_url, proxy_base)

    # Extract title
    title_match = re.search(r"<title[^>]*>(.*?)</title>", processed, re.IGNORECASE | re.DOTALL)
    title = title_match.group(1).strip() if title_match else ""

    # Store in cache, return short token
    token = _cache_put(processed, base_url, title)

    return {
        "success": True,
        "view_url": f"/api/autofill/view?t={token}",
        "final_url": base_url,
        "title": title,
    }


@router.get("/view")
def autofill_view(t: str = Query(default="", description="View token")):
    """Serve the processed page for iframe loading."""
    if not t:
        raise HTTPException(status_code=400, detail="缺少页面令牌")
    entry = _cache_get(t)
    if not entry:
        raise HTTPException(status_code=400, detail="页面数据无效或已过期（10 分钟有效）")
    return HTMLResponse(content=entry["html"])


# ── AI matching ──────────────────────────────────────────────────

class AIMatchRequest(BaseModel):
    profile_id: str
    fields: list  # from detect-fields output
    mode: str = "full"  # "full" or "incremental"


@router.post("/ai-match")
def ai_match(body: AIMatchRequest, user: dict = Depends(auth_module.get_current_user)):
    """Use configured AI to map page fields to resume profile fields."""
    profiles = _load_profiles(user["user_id"])
    if body.profile_id not in profiles:
        raise HTTPException(status_code=404, detail="简历模板不存在")

    profile = profiles[body.profile_id]
    profile_fields = profile.get("fields", {})

    # Build field list with options for the AI
    field_desc = []
    for f in body.fields:
        d = f"{f.get('label') or f.get('name') or f.get('id') or '(unknown)'}"
        d += f" [type={f.get('type','text')}]"
        if f.get("options"):
            d += f" options={[o['text'] for o in f['options'][:10]]}"
        if f.get("placeholder"):
            d += f" placeholder=\"{f['placeholder']}\""
        if f.get("required"):
            d += " required"
        field_desc.append(d)

    profile_desc = "\n".join(f"- {k}: {v}" for k, v in profile_fields.items() if v)

    system_prompt = """你是一个表单字段映射专家。给定：
1. 一个候选人简历数据（字段名: 值）
2. 一个目标网页上的表单字段列表

请将每个表单字段映射到最合适的简历字段，或者标记为"skip"。

返回严格的 JSON 数组，每个元素包含：
- page_field_index: 表单字段在输入列表中的索引（从0开始）
- profile_field: 简历字段名（必须是提供的简历数据中存在的字段名，或"skip"）
- value: 应填入的值（从简历数据中取，可以适当调整格式以匹配表单字段类型）
- confidence: 0-100 的置信度

注意：
- 对于下拉框(select)，选择最匹配的选项值
- 对于日期字段，将日期格式化为 YYYY-MM-DD 或 YYYY-MM
- 对于性别字段，将"男"/"女"映射为页面上的对应值
- 只映射有明确对应关系的字段，不确定的设为"skip"
- 只返回 JSON 数组，不要其他内容"""

    user_content = f"""简历数据：
{profile_desc}

表单字段列表：
{chr(10).join(f"[{i}] {d}" for i, d in enumerate(field_desc))}"""

    # Use configured AI provider
    cfg = database.get_user_config(user["user_id"])
    provider = cfg.get("ai_provider") or "deepseek"
    if provider not in ("deepseek", "openai", "anthropic", "kimi"):
        provider = "deepseek"

    key_field = f"{provider}_api_key"
    model_field = f"{provider}_model"
    model_default = {
        "deepseek": "deepseek-v4-flash", "openai": "gpt-5.4-mini",
        "anthropic": "claude-sonnet-5", "kimi": "kimi-k3",
    }[provider]

    api_key = cfg.get(key_field, "")
    if not api_key:
        raise HTTPException(status_code=400, detail=f"请先在 AI 配置中填写 API Key")

    model = cfg.get(model_field, "") or model_default
    base_url = cfg.get(f"{provider}_base_url", "") or DEFAULT_BASE_URLS.get(provider, "")
    api_mode = cfg.get("openai_api_mode", "") or "responses"

    safe_base = validate_public_base_url(base_url, provider)

    try:
        if provider == "openai" and api_mode == "chat_completions":
            resp = requests.post(
                endpoint_url(safe_base, "chat/completions"),
                headers=auth_headers(provider, api_key),
                json={
                    "model": model,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_content},
                    ],
                    "stream": False, "temperature": 0.1, "max_tokens": 4000,
                },
                timeout=60, allow_redirects=False,
            )
        elif provider == "openai":
            resp = requests.post(
                endpoint_url(safe_base, "responses"),
                headers=auth_headers(provider, api_key),
                json={
                    "model": model,
                    "instructions": system_prompt,
                    "input": user_content,
                    "max_output_tokens": 4000,
                },
                timeout=60, allow_redirects=False,
            )
        elif provider == "anthropic":
            resp = requests.post(
                endpoint_url(safe_base, "messages"),
                headers=auth_headers(provider, api_key),
                json={
                    "model": model,
                    "max_tokens": 4000,
                    "system": system_prompt,
                    "messages": [{"role": "user", "content": user_content}],
                },
                timeout=60, allow_redirects=False,
            )
        else:
            resp = requests.post(
                endpoint_url(safe_base, "chat/completions"),
                headers=auth_headers(provider, api_key),
                json={
                    "model": model,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_content},
                    ],
                    "stream": False, "temperature": 0.1,
                },
                timeout=60, allow_redirects=False,
            )

        if not resp.ok:
            raise HTTPException(status_code=502, detail=f"AI API 请求失败：HTTP {resp.status_code}")

        payload = resp.json()
        if provider == "openai" and api_mode != "chat_completions":
            text = ""
            for item in payload.get("output") or []:
                if isinstance(item, dict) and item.get("type") == "message":
                    for c in item.get("content") or []:
                        if isinstance(c, dict) and c.get("type") == "output_text":
                            text += str(c.get("text") or "")
        elif provider == "anthropic":
            text = "\n".join(
                str(b.get("text") or "")
                for b in payload.get("content") or []
                if isinstance(b, dict) and b.get("type") == "text"
            )
        else:
            text = str(payload["choices"][0]["message"]["content"])

        # Extract JSON from response
        json_match = re.search(r"\[.*\]", text, re.DOTALL)
        if not json_match:
            raise HTTPException(status_code=502, detail="AI 未返回有效的 JSON 映射结果")

        mappings = json.loads(json_match.group(0))
    except HTTPException:
        raise
    except requests.RequestException as exc:
        raise HTTPException(status_code=502, detail=f"AI API 连接失败：{exc}")
    except (KeyError, IndexError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=502, detail=f"AI 返回格式异常：{exc}")

    # Build fill commands
    fills = []
    for m in mappings:
        idx = m.get("page_field_index", -1)
        pf = m.get("profile_field", "")
        val = m.get("value", "")
        conf = m.get("confidence", 0)

        if pf == "skip" or idx < 0 or idx >= len(body.fields) or conf < 30:
            continue

        field_info = body.fields[idx]
        normalized = _normalize_field_value(pf, val, field_info)
        fills.append({
            "page_field_index": idx,
            "profile_field": pf,
            "value": normalized,
            "confidence": conf,
            "page_field": field_info,
        })

    return {
        "success": True,
        "mappings": fills,
        "total_page_fields": len(body.fields),
        "mapped_count": len(fills),
        "provider": provider,
        "model": model,
    }


# ── Extension API ─────────────────────────────────────────────────

class ExtensionMatchRequest(BaseModel):
    fields: list
    profile_id: str


@router.post("/extension/match")
def extension_match(body: ExtensionMatchRequest, user: dict = Depends(auth_module.get_current_user)):
    """Lightweight AI match for browser extension — returns fill commands."""
    profiles = _load_profiles(user["user_id"])
    if body.profile_id not in profiles:
        raise HTTPException(status_code=404, detail="简历模板不存在")
    profile = profiles[body.profile_id]
    profile_fields = profile.get("fields", {})

    # Use rule-based matching (fast, no API call needed)
    fills = []
    for f in body.fields:
        label = (f.get("label") or "").lower()
        name = (f.get("name") or "").lower()
        uid = (f.get("id") or "").lower()
        placeholder = (f.get("placeholder") or "").lower()
        best_field, best_score = None, 0
        for pk, aliases in FIELD_ALIASES.items():
            if pk not in profile_fields or not profile_fields[pk]:
                continue
            for alias in aliases:
                a = alias.lower()
                if a in label: score = 95
                elif a == name: score = 85
                elif a in uid: score = 75
                elif a in placeholder: score = 65
                else: continue
                if score > best_score:
                    best_score, best_field = score, pk
        if best_field and best_score >= 65:
            fills.append({
                "page_field_index": body.fields.index(f),
                "profile_field": best_field,
                "value": _normalize_field_value(best_field, profile_fields[best_field], f),
                "confidence": best_score,
            })

    return {
        "success": True,
        "mappings": fills,
        "total_page_fields": len(body.fields),
        "mapped_count": len(fills),
    }


@router.get("/extension/config")
def extension_config(user: dict = Depends(auth_module.get_current_user)):
    """Return all data the extension needs: profiles + AI settings."""
    profiles = _load_profiles(user["user_id"])
    profile_list = [
        {"id": pid, "name": p.get("name", pid), "fields": p.get("fields", {})}
        for pid, p in profiles.items()
    ]

    cfg = database.get_user_config(user["user_id"])
    provider = cfg.get("ai_provider") or "deepseek"
    key_field = f"{provider}_api_key"
    model_field = f"{provider}_model"
    base_field = f"{provider}_base_url"

    return {
        "success": True,
        "profiles": profile_list,
        "server_url": "https://www.toudimianban.cloud",
        "ai_provider": provider,
        "has_ai_key": bool(cfg.get(key_field, "")),
        "ai_model": cfg.get(model_field, "") or {
            "deepseek": "deepseek-v4-flash", "openai": "gpt-5.4-mini",
            "anthropic": "claude-sonnet-5", "kimi": "kimi-k3",
        }.get(provider, ""),
    }


@router.get("/extension/version")
def extension_version():
    """Return latest extension version so the extension can check for updates."""
    return {
        "version": "1.0",
        "download_url": "https://www.toudimianban.cloud/api/autofill/extension/download",
        "changelog": "初始版本",
    }


@router.get("/extension/download")
def download_extension():
    """Download the browser extension as a zip file."""
    ext_dir = PROJECT_DIR / "extension"
    if not ext_dir.is_dir():
        raise HTTPException(status_code=404, detail="扩展目录不存在")

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for file_path in ext_dir.rglob("*"):
            if file_path.name.startswith(".") or "__pycache__" in file_path.parts:
                continue
            if file_path.is_file():
                arcname = str(file_path.relative_to(ext_dir))
                zf.write(file_path, arcname)

    buf.seek(0)
    return Response(
        content=buf.getvalue(),
        media_type="application/zip",
        headers={"Content-Disposition": "attachment; filename=autofill-extension.zip"},
    )
