import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


MODULE_PATH = Path(__file__).parents[1] / "tools" / "offershow_scraper.py"
SPEC = importlib.util.spec_from_file_location("offershow_scraper", MODULE_PATH)
offershow = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(offershow)


class OfferShowScraperTests(unittest.TestCase):
    def test_flattens_catalog_and_deduplicates_reports(self):
        scraper = offershow.OfferShowScraper(interval=0.5)
        module = {
            "module_id": 1, "module_title": "校招薪酬", "total": 1,
            "company_list": [{
                "company_name": "示例公司",
                "salary_list": [{"uuid": "u1", "company": "示例公司", "title": "2026薪资"}],
            }],
        }
        with patch.object(scraper, "fetch_catalog_page", return_value=[module]):
            records = scraper.scrape(max_pages=1)
        scraper.close()
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["company"], "示例公司")

    def test_parses_detail_json(self):
        scraper = offershow.OfferShowScraper(interval=0.5)
        payload = {"detail_json": json.dumps({"positions": [{"name": "研发", "normal": "20*15"}]})}
        with patch.object(scraper, "_post", return_value=payload):
            detail = scraper.fetch_detail("u1")
        scraper.close()
        self.assertEqual(detail["positions"][0]["normal"], "20*15")

    def test_exports_utf8_json_with_attribution(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "result.json"
            offershow.export_json([{"uuid": "u1"}], target)
            payload = json.loads(target.read_text(encoding="utf-8"))
        self.assertEqual(payload["source"], "OfferShow")
        self.assertIn("个人查询", payload["attribution"])

    def test_searches_salary_disclosures_with_token(self):
        scraper = offershow.OfferShowScraper(interval=0.5)
        response = unittest.mock.Mock()
        response.raise_for_status.return_value = None
        response.json.return_value = {"code": -1, "data": {"salarys": [{"company": "小鹏"}]}}
        with patch.object(scraper.session, "post", return_value=response) as request:
            rows = scraper.search_salary_disclosures(token="token", keyword="小鹏")
        scraper.close()
        self.assertEqual(rows[0]["company"], "小鹏")
        self.assertEqual(request.call_args.kwargs["headers"]["appVersion"], "2")
        self.assertEqual(request.call_args.kwargs["data"]["search_priority"], 1)
        self.assertNotIn("limit", request.call_args.kwargs["data"])


if __name__ == "__main__":
    unittest.main()
