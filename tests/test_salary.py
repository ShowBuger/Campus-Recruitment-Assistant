import unittest
import tempfile
from pathlib import Path
from unittest.mock import patch

from app.routers.salary import _compact, _effective_offershow_token, _format_offer_salary, _mask_contact, _mask_token, _matches_offershow_filters, _offershow_publish_year, _search, _write_offershow_token


class SalarySearchTests(unittest.TestCase):
    def setUp(self):
        self.records = [
            {"company": "示例科技", "salary": "20k*15", "city": "深圳", "education": "211硕", "job": "嵌入式软件", "note": "双休"},
            {"company": "另一家公司", "salary": "18k*14", "city": "杭州", "education": "双非硕", "job": "驱动开发", "note": ""},
        ]

    def test_searches_across_salary_fields(self):
        result = _search(self.records, "20k", "", "", "", "")
        self.assertEqual([item["company"] for item in result], ["示例科技"])

    def test_combines_structured_filters(self):
        result = _search(self.records, "", "示例", "深圳", "211", "嵌入式")
        self.assertEqual(len(result), 1)

    def test_masks_phone_numbers_in_public_notes(self):
        self.assertNotIn("13800138000", _mask_contact("微信：13800138000"))

    def test_formats_offershow_salary_levels(self):
        value = _format_offer_salary({"name": "研发", "normal": "20k*15", "sp": "25k*15"})
        self.assertEqual(value, "普通：20k*15 / SP：25k*15")

    def test_normalized_identity_handles_salary_punctuation(self):
        self.assertEqual(_compact("小鹏汽车 20K × 15"), "小鹏汽车20k15")

    def test_masks_and_saves_offershow_token_securely(self):
        token = "header.payload.signature"
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "token"
            with patch("app.routers.salary.OFFERSHOW_TOKEN_PATH", str(target)):
                _write_offershow_token(token)
            self.assertEqual(target.read_text(encoding="utf-8").strip(), token)
            self.assertEqual(target.stat().st_mode & 0o777, 0o600)
        self.assertNotEqual(_mask_token(token), token)

    def test_personal_offershow_token_overrides_public_token(self):
        with patch("app.routers.salary.database.get_user_config", return_value={"offershow_access_token": "personal.token.value"}), patch("app.routers.salary._read_offershow_token", return_value="public.token.value"):
            token, personal = _effective_offershow_token(7)
        self.assertEqual(token, "personal.token.value")
        self.assertTrue(personal)

    def test_uses_offershow_actual_publish_year(self):
        self.assertEqual(_offershow_publish_year({"publish_time": "2023-05-16 13:53:20", "time": "2021-12"}), "2023")

    def test_combines_offershow_company_job_and_city_filters(self):
        record = {"company": "大疆创新", "job": "嵌入式开发", "city": "深圳"}
        self.assertTrue(_matches_offershow_filters(record, "大疆", "嵌入式", "深圳"))
        self.assertFalse(_matches_offershow_filters(record, "大疆", "算法", "深圳"))


if __name__ == "__main__":
    unittest.main()
