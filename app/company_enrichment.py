"""Web evidence collection and safe parsing for company/job enrichment."""

from __future__ import annotations

import json
import re
import xml.etree.ElementTree as ET
from html.parser import HTMLParser
from urllib.parse import quote, urlparse

import requests


SEARCH_URL = "https://www.so.com/s"
FALLBACK_SEARCH_URL = "https://www.bing.com/search"
WIKIPEDIA_API_URL = "https://zh.wikipedia.org/w/api.php"
USER_AGENT = "CampusRecruitmentAssistant/1.0"


class EnrichmentError(RuntimeError):
    pass


class _SoResultParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.results = []
        self.current = None
        self.in_heading = False
        self.in_link = False
        self.in_description = False

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        classes = set((attributes.get("class") or "").split())
        if tag == "h3" and "res-title" in classes:
            self._finish()
            self.current = {"title": "", "url": "", "snippet": ""}
            self.in_heading = True
        elif tag == "a" and self.in_heading and self.current is not None:
            self.in_link = True
            self.current["url"] = attributes.get("data-mdurl") or attributes.get("href") or ""
        elif tag == "p" and "res-desc" in classes and self.current is not None:
            self.in_description = True

    def handle_endtag(self, tag):
        if tag == "a":
            self.in_link = False
        elif tag == "h3":
            self.in_heading = False
        elif tag == "p" and self.in_description:
            self.in_description = False
            self._finish()

    def handle_data(self, data):
        if self.current is None:
            return
        if self.in_link:
            self.current["title"] += data
        elif self.in_description:
            self.current["snippet"] += data

    def close(self):
        super().close()
        self._finish()

    def _finish(self):
        if self.current and self.current["title"].strip() and self.current["url"].strip():
            self.results.append(self.current)
        self.current = None


class _BingResultParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.results = []
        self.current = None
        self.in_heading = False
        self.in_link = False
        self.in_description = False

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        classes = set((attributes.get("class") or "").split())
        if tag == "li" and "b_algo" in classes:
            self._finish()
            self.current = {"title": "", "url": "", "snippet": ""}
        elif tag == "h2" and self.current is not None:
            self.in_heading = True
        elif tag == "a" and self.in_heading and self.current is not None:
            self.in_link = True
            self.current["url"] = attributes.get("href") or ""
        elif tag == "p" and self.current is not None:
            self.in_description = True

    def handle_endtag(self, tag):
        if tag == "a":
            self.in_link = False
        elif tag == "h2":
            self.in_heading = False
        elif tag == "p":
            self.in_description = False
        elif tag == "li" and self.current is not None:
            self._finish()

    def handle_data(self, data):
        if self.current is None:
            return
        if self.in_link:
            self.current["title"] += data
        elif self.in_description:
            self.current["snippet"] += data

    def close(self):
        super().close()
        self._finish()

    def _finish(self):
        if self.current and self.current["title"].strip() and self.current["url"].strip():
            self.results.append(self.current)
        self.current = None


def _compact(value: str) -> str:
    return re.sub(r"[^0-9a-z\u4e00-\u9fff]+", "", (value or "").casefold())


def _company_terms(company: str) -> list[str]:
    compact = _compact(company)
    for suffix in ("有限责任公司", "股份有限公司", "有限公司", "集团", "公司"):
        suffix_key = _compact(suffix)
        if compact.endswith(suffix_key) and len(compact) > len(suffix_key):
            compact = compact[:-len(suffix_key)]
            break
    terms = [compact]
    if len(compact) >= 6:
        terms.append(compact[-4:])
    if len(compact) >= 4:
        terms.append(compact[:2])
    return list(dict.fromkeys(term for term in terms if len(term) >= 2))


def _job_terms(job: str) -> list[str]:
    return list(dict.fromkeys(
        term for term in re.split(r"[^0-9a-z\u4e00-\u9fff+#]+", (job or "").casefold())
        if len(term) >= 2
    ))


def _relevant(item: dict[str, str], company: str, job: str = "") -> bool:
    haystack = _compact(item.get("title", "") + item.get("snippet", ""))
    terms = _company_terms(company)
    if terms and terms[0] in haystack:
        return True
    if any(term in haystack for term in terms[1:] if len(term) >= 3):
        return True
    short_terms = [term for term in terms if len(term) == 2]
    short_match = any(term in haystack for term in short_terms)
    if not short_match:
        return False
    raw_text = item.get("title", "") + item.get("snippet", "")
    job_match = any(_compact(term) in haystack for term in _job_terms(job))
    company_context = bool(re.search(r"公司|集团|科技|招聘|岗位|工程师", raw_text))
    return job_match or company_context


def _search_so(query: str) -> list[dict[str, str]]:
    response = requests.get(
        SEARCH_URL,
        params={"q": query},
        headers={"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/124 Safari/537.36"},
        timeout=20,
        allow_redirects=True,
    )
    response.raise_for_status()
    parser = _SoResultParser()
    parser.feed(response.text)
    parser.close()
    return parser.results


def _search_bing_rss(query: str) -> list[dict[str, str]]:
    response = requests.get(
        FALLBACK_SEARCH_URL,
        params={"q": query, "format": "rss"},
        headers={"User-Agent": USER_AGENT, "Accept": "application/rss+xml, application/xml"},
        timeout=20,
        allow_redirects=False,
    )
    response.raise_for_status()
    root = ET.fromstring(response.content)
    return [{
        "title": (item.findtext("title") or "").strip(),
        "url": (item.findtext("link") or "").strip(),
        "snippet": re.sub(r"\s+", " ", item.findtext("description") or "").strip(),
    } for item in root.findall("./channel/item")[:8]]


def _search_bing_html(query: str) -> list[dict[str, str]]:
    response = requests.get(
        FALLBACK_SEARCH_URL,
        params={"q": query, "setlang": "zh-hans", "cc": "cn"},
        headers={
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/124 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml",
        },
        timeout=20,
        allow_redirects=True,
    )
    response.raise_for_status()
    parser = _BingResultParser()
    parser.feed(response.text)
    parser.close()
    return parser.results[:8]


def _search_wikipedia(company: str) -> list[dict[str, str]]:
    response = requests.get(
        WIKIPEDIA_API_URL,
        params={
            "action": "query", "list": "search", "srsearch": company,
            "format": "json", "utf8": 1, "srlimit": 5,
        },
        headers={"User-Agent": f"{USER_AGENT} (contact: admin@toudimianban.cloud)"},
        timeout=15,
    )
    response.raise_for_status()
    items = response.json().get("query", {}).get("search", [])
    results = []
    for item in items:
        title = str(item.get("title") or "").strip()
        snippet = re.sub(r"<[^>]+>", "", str(item.get("snippet") or ""))
        if not title or _compact(title) != _compact(company):
            continue
        results.append({
            "title": f"维基百科：{title}",
            "url": "https://zh.wikipedia.org/wiki/" + quote(title.replace(" ", "_")),
            "snippet": re.sub(r"\s+", " ", snippet).strip(),
        })
    return results


def search_company_job(company: str, job: str) -> list[dict[str, str]]:
    queries = [
        f'"{company}" 公司 官网 主营业务',
        f'"{company}" "{job}" 招聘 岗位',
        f"{company} 招聘 公司介绍",
    ]
    results: list[dict[str, str]] = []
    seen: set[str] = set()
    search_succeeded = False
    errors: list[str] = []

    def add_candidates(candidates: list[dict[str, str]]) -> int:
        added = 0
        for item in candidates[:8]:
            title = re.sub(r"\s+", " ", item.get("title") or "").strip()
            url = (item.get("url") or "").strip()
            snippet = re.sub(r"\s+", " ", item.get("snippet") or "").strip()
            parsed = urlparse(url)
            if (
                parsed.scheme not in {"http", "https"} or not parsed.hostname
                or url in seen or not _relevant(
                    {"title": title, "snippet": snippet}, company, job
                )
            ):
                continue
            seen.add(url)
            results.append({"title": title[:200], "url": url[:1000], "snippet": snippet[:800]})
            added += 1
        return added

    try:
        wikipedia_results = _search_wikipedia(company)
        search_succeeded = True
        add_candidates(wikipedia_results)
    except (requests.RequestException, ValueError, TypeError) as exc:
        errors.append(str(exc))

    queries_to_run = queries[1:2] if results else queries
    for query in queries_to_run:
        for searcher in (_search_so, _search_bing_html, _search_bing_rss):
            try:
                candidates = searcher(query)
                search_succeeded = True
            except (requests.RequestException, ET.ParseError) as exc:
                errors.append(str(exc))
                candidates = []
            if add_candidates(candidates):
                break
    if not results:
        if not search_succeeded and errors:
            raise EnrichmentError(f"联网搜索失败：{errors[-1]}")
        return []
    return results[:10]


def evidence_text(results: list[dict[str, str]]) -> str:
    blocks = []
    for index, item in enumerate(results, 1):
        blocks.append(
            f"[{index}] 标题：{item['title']}\n"
            f"网址：{item['url']}\n"
            f"摘要：{item['snippet']}"
        )
    return "\n\n".join(blocks)


def _json_object(text: str) -> dict:
    cleaned = (text or "").strip()
    cleaned = cleaned.lstrip("\ufeff")
    fenced = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", cleaned, flags=re.IGNORECASE)
    if fenced:
        cleaned = fenced.group(1).strip()
    try:
        payload = json.loads(cleaned)
    except json.JSONDecodeError:
        match = re.search(r"\{[\s\S]*\}", cleaned)
        if not match:
            raise EnrichmentError("AI 未返回结构化补全结果")
        try:
            payload = json.loads(match.group(0))
        except json.JSONDecodeError as exc:
            raise EnrichmentError("AI 补全结果不是有效 JSON") from exc
    if not isinstance(payload, dict):
        raise EnrichmentError("AI 补全结果格式不正确")
    return payload


def parse_result(
    text: str,
    evidence: list[dict[str, str]],
    *,
    allow_unsourced_note: bool = False,
    allow_empty: bool = False,
) -> dict:
    payload = _json_object(text)
    company_type = str(payload.get("company_type") or "").strip()[:30]
    raw_directions = payload.get("directions") or []
    if not isinstance(raw_directions, list):
        raw_directions = [raw_directions]
    directions = list(dict.fromkeys(
        str(item).strip()[:30] for item in raw_directions if str(item).strip()
    ))[:3]
    note_append = str(payload.get("note_append") or "").strip()[:800]
    allowed = {item["url"]: item for item in evidence}
    sources = []
    for source in payload.get("sources") or []:
        if not isinstance(source, dict):
            continue
        url = str(source.get("url") or "").strip()
        if url not in allowed or any(item["url"] == url for item in sources):
            continue
        sources.append({"title": allowed[url]["title"], "url": url})
        if len(sources) == 5:
            break
    if note_append and not sources and not allow_unsourced_note:
        note_append = ""
    if not any((company_type, directions, note_append)):
        if not allow_empty:
            raise EnrichmentError("公开信息不足，AI 未生成可用的补全内容")
    return {
        "company_type": company_type,
        "directions": directions,
        "note_append": note_append,
        "sources": sources,
        "knowledge_based": allow_unsourced_note and not sources,
    }


def appended_note(existing: str, result: dict, stamp: str) -> str:
    note = result.get("note_append") or ""
    if not note:
        return existing
    source_lines = [
        f"- {item['title']}：{item['url']}" for item in result.get("sources") or []
    ]
    label = "AI 知识补全" if result.get("knowledge_based") else "AI 补全"
    section = f"[{label} · {stamp}]\n{note}"
    if source_lines:
        section += "\n参考来源：\n" + "\n".join(source_lines)
    # The same enrichment can be generated with a different date or source
    # formatting. Compare the actual note body as well to prevent repeated
    # clicks from growing the user's notes indefinitely.
    normalized_note = re.sub(r"\s+", "", note)
    normalized_existing = re.sub(r"\s+", "", existing or "")
    if section in existing or (normalized_note and normalized_note in normalized_existing):
        return existing
    merged = (existing.rstrip() + "\n\n" + section).strip() if existing.strip() else section
    return merged[:5000]
