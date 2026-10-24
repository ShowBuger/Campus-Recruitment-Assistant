#!/usr/bin/env python3
"""Low-frequency OfferShow salary-report collector for personal/internal use.

The public website states that its salary data may be used for personal lookup
and internal enterprise use, but may not be republished commercially without
authorization. This tool does not bypass login, membership, or access controls.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


BASE_URL = "https://www.offershow.cn"
CATALOG_PATH = "/api/od/search_salary_list_by_company"
DETAIL_PATH = "/api/mp/get_salary_list_detail"
DISCLOSURE_SEARCH_URL = f"{BASE_URL}/offershow/uuid/search_salary_cutword"
SUCCESS_CODES = {0, 200001}
ATTRIBUTION = "数据源自 OfferShow，仅供个人查询与企业内部使用"


class OfferShowError(RuntimeError):
    pass


class OfferShowScraper:
    def __init__(self, *, interval: float = 1.5, timeout: float = 20.0, retries: int = 3):
        if interval < 0.5:
            raise ValueError("请求间隔不能小于 0.5 秒")
        self.interval = interval
        self.timeout = timeout
        self._last_request_at = 0.0
        retry = Retry(
            total=retries,
            connect=retries,
            read=retries,
            status=retries,
            backoff_factor=1.0,
            status_forcelist=(429, 500, 502, 503, 504),
            allowed_methods=frozenset(("POST",)),
            respect_retry_after_header=True,
        )
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Campus-Recruitment-Assistant/OfferShowCollector (+personal-internal-use)",
            "Accept": "application/json, text/plain, */*",
            "Referer": f"{BASE_URL}/jobs/offerlist",
            "Origin": BASE_URL,
        })
        self.session.mount("https://", HTTPAdapter(max_retries=retry))

    def close(self) -> None:
        self.session.close()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()

    def _throttle(self) -> None:
        remaining = self.interval - (time.monotonic() - self._last_request_at)
        if remaining > 0:
            time.sleep(remaining)

    def _post(self, path: str, *, params: dict | None = None, data: dict | None = None) -> object:
        self._throttle()
        try:
            response = self.session.post(
                BASE_URL + path,
                params=params,
                data=data or {},
                timeout=self.timeout,
            )
            self._last_request_at = time.monotonic()
            response.raise_for_status()
            payload = response.json()
        except requests.RequestException as exc:
            raise OfferShowError(f"请求 OfferShow 失败：{exc}") from exc
        except ValueError as exc:
            raise OfferShowError("OfferShow 返回了非 JSON 数据") from exc
        if not isinstance(payload, dict):
            raise OfferShowError("OfferShow 返回的数据格式异常")
        if payload.get("code") not in SUCCESS_CODES:
            raise OfferShowError(str(payload.get("msg") or f"接口错误码 {payload.get('code')}"))
        return payload.get("data")

    def fetch_catalog_page(self, *, module_id: int, page: int, size: int, search: str = "") -> list[dict]:
        data = self._post(
            CATALOG_PATH,
            params={"page": page, "size": size},
            data={"module_id": module_id, "search_content": search, "page": page, "size": size},
        )
        if not isinstance(data, list):
            raise OfferShowError("薪酬报告目录格式异常")
        return [item for item in data if isinstance(item, dict)]

    def fetch_detail(self, report_uuid: str) -> dict:
        data = self._post(DETAIL_PATH, data={"uuid": report_uuid})
        if not isinstance(data, dict):
            raise OfferShowError(f"报告 {report_uuid} 的详情格式异常")
        detail = {}
        raw_detail = data.get("detail_json")
        if isinstance(raw_detail, str) and raw_detail.strip():
            try:
                detail = json.loads(raw_detail)
            except json.JSONDecodeError as exc:
                raise OfferShowError(f"报告 {report_uuid} 的 detail_json 无法解析") from exc
        header = detail.get("header") or {}
        if isinstance(header, list):
            header = header[0] if header else {}
        return {
            "header": header if isinstance(header, dict) else {},
            "positions": [item for item in detail.get("positions", []) if isinstance(item, dict)],
            "notes": [str(item) for item in detail.get("notes", []) if str(item).strip()],
        }

    def search_salary_disclosures(
        self, *, token: str, keyword: str
    ) -> list[dict]:
        """Search user-submitted salary disclosures with an authorized OfferShow token."""
        if not token.strip():
            raise OfferShowError("未配置 OfferShow 登录凭证")
        self._throttle()
        try:
            response = self.session.post(
                DISCLOSURE_SEARCH_URL,
                headers={"accessToken": token.strip(), "appVersion": "2"},
                data={
                    "content": keyword,
                    "ordertype": 2,
                    "search_priority": 1,
                    "part_school": "",
                    "xueli": "",
                    "year": "",
                },
                timeout=self.timeout,
            )
            self._last_request_at = time.monotonic()
            response.raise_for_status()
            payload = response.json()
        except requests.RequestException as exc:
            raise OfferShowError(f"请求 OfferShow 薪资爆料失败：{exc}") from exc
        except ValueError as exc:
            raise OfferShowError("OfferShow 薪资爆料接口返回了非 JSON 数据") from exc
        data = payload.get("data") if isinstance(payload, dict) else None
        rows = data.get("salarys") if isinstance(data, dict) else None
        if not isinstance(rows, list):
            message = payload.get("msg") if isinstance(payload, dict) else "返回格式异常"
            raise OfferShowError(str(message or "OfferShow 薪资爆料查询失败"))
        return [row for row in rows if isinstance(row, dict)]

    @staticmethod
    def _catalog_reports(module: dict) -> Iterator[dict]:
        for company in module.get("company_list") or []:
            if not isinstance(company, dict):
                continue
            company_name = str(company.get("company_name") or "").strip()
            for report in company.get("salary_list") or []:
                if not isinstance(report, dict) or not report.get("uuid"):
                    continue
                yield {
                    "uuid": str(report["uuid"]),
                    "company": str(report.get("company") or company_name),
                    "title": str(report.get("title") or ""),
                    "year": str(report.get("year") or ""),
                    "release_time": str(report.get("release_time") or ""),
                    "logo": str(report.get("logo") or company.get("company_logo") or ""),
                    "source_url": f"{BASE_URL}/jobs/offer-list-detail/{report['uuid']}",
                    "module_id": module.get("module_id"),
                    "module_title": str(module.get("module_title") or ""),
                }

    def scrape(self, *, search: str = "", page_size: int = 15, max_pages: int = 10, with_details: bool = False, show_progress: bool = False) -> list[dict]:
        if not 1 <= page_size <= 50:
            raise ValueError("page_size 必须在 1 到 50 之间")
        if max_pages < 1:
            raise ValueError("max_pages 必须至少为 1")
        first_modules = self.fetch_catalog_page(module_id=0, page=1, size=page_size, search=search)
        reports: dict[str, dict] = {}
        for first_module in first_modules:
            module_id = int(first_module.get("module_id") or 0)
            total = max(0, int(first_module.get("total") or 0))
            page_count = min(max_pages, max(1, math.ceil(total / page_size)))
            modules = [first_module]
            for page in range(2, page_count + 1):
                page_modules = self.fetch_catalog_page(
                    module_id=module_id, page=page, size=page_size, search=search
                )
                selected = next(
                    (item for item in page_modules if int(item.get("module_id") or 0) == module_id),
                    page_modules[0] if page_modules else None,
                )
                if not selected:
                    break
                modules.append(selected)
            for module in modules:
                for report in self._catalog_reports(module):
                    reports[report["uuid"]] = report
        output = list(reports.values())
        if with_details:
            for index, report in enumerate(output, 1):
                report["detail"] = self.fetch_detail(report["uuid"])
                if show_progress:
                    print(f"详情进度 {index}/{len(output)}：{report['title']}")
        return output


def export_json(records: list[dict], path: Path) -> None:
    payload = {
        "source": "OfferShow",
        "source_url": f"{BASE_URL}/jobs/offerlist",
        "attribution": ATTRIBUTION,
        "collected_at": datetime.now(timezone.utc).isoformat(),
        "count": len(records),
        "records": records,
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def export_csv(records: list[dict], path: Path) -> None:
    fieldnames = [
        "uuid", "company", "title", "year", "release_time", "position",
        "normal", "sp", "ssp", "source_url", "module_title",
    ]
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for record in records:
            positions = (record.get("detail") or {}).get("positions") or [{}]
            for position in positions:
                writer.writerow({
                    "uuid": record.get("uuid", ""), "company": record.get("company", ""),
                    "title": record.get("title", ""), "year": record.get("year", ""),
                    "release_time": record.get("release_time", ""),
                    "position": position.get("name", ""), "normal": position.get("normal", ""),
                    "sp": position.get("sp", ""), "ssp": position.get("ssp", ""),
                    "source_url": record.get("source_url", ""),
                    "module_title": record.get("module_title", ""),
                })


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="低频采集 OfferShow 公开薪酬报告目录与详情")
    parser.add_argument("--search", default="", help="按公司搜索，例如：腾讯")
    parser.add_argument("--page-size", type=int, default=15, help="目录每页公司数，1-50")
    parser.add_argument("--max-pages", type=int, default=10, help="每个目录模块最多采集页数")
    parser.add_argument("--interval", type=float, default=1.5, help="请求最小间隔秒数，不得低于 0.5")
    parser.add_argument("--with-details", action="store_true", help="逐份读取岗位薪资详情")
    parser.add_argument("--output", type=Path, default=Path("offershow_salary_reports.json"))
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        with OfferShowScraper(interval=args.interval) as scraper:
            records = scraper.scrape(
                search=args.search,
                page_size=args.page_size,
                max_pages=args.max_pages,
                with_details=args.with_details,
                show_progress=True,
            )
        args.output.parent.mkdir(parents=True, exist_ok=True)
        if args.output.suffix.casefold() == ".csv":
            export_csv(records, args.output)
        else:
            export_json(records, args.output)
        print(f"完成：{len(records)} 份薪酬报告已保存到 {args.output}")
        print(ATTRIBUTION)
        return 0
    except (OfferShowError, ValueError) as exc:
        print(f"采集失败：{exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
