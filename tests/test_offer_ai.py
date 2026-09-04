import unittest
from unittest.mock import patch

from fastapi import HTTPException

from app.routers import ai


class OfferAiComparisonTests(unittest.TestCase):
    @staticmethod
    def record(company):
        return {"fields": {
            "公司名称": company,
            "秋招岗位": "研发工程师",
            "城市": "上海",
            "优先级": "⭐⭐⭐",
            "Offer详情": {"base_annual": 240000, "growth_score": 8},
        }}

    def test_comparison_uses_current_users_records_and_provider(self):
        records = {"rec-a": self.record("甲公司"), "rec-b": self.record("乙公司")}
        config = {
            "ai_provider": "deepseek", "deepseek_api_key": "secret",
            "deepseek_model": "deepseek-test", "deepseek_base_url": "https://api.deepseek.com",
        }
        with (
            patch("app.routers.ai.local_records.get_record", side_effect=lambda user_id, record_id: records.get(record_id)) as get_record,
            patch("app.routers.ai.database.get_user_config", return_value=config),
            patch("app.routers.ai._call_ai_provider", return_value="# AI 深度分析结论\n\n建议选择甲公司。") as call_ai,
        ):
            result = ai.compare_offers_with_ai(
                ai.OfferComparisonRequest(record_ids=["rec-a", "rec-b"], weights={"growth": 60}),
                user={"user_id": 7},
            )
        self.assertEqual([item.args[0] for item in get_record.call_args_list], [7, 7])
        self.assertIn("甲公司", call_ai.call_args.args[4])
        self.assertIn("AI 深度分析结论", result["analysis_html"])
        self.assertEqual(result["model"], "deepseek-test")

    def test_comparison_rejects_records_outside_current_user(self):
        with patch("app.routers.ai.local_records.get_record", return_value=None):
            with self.assertRaises(HTTPException) as raised:
                ai.compare_offers_with_ai(
                    ai.OfferComparisonRequest(record_ids=["rec-a", "rec-b"]),
                    user={"user_id": 7},
                )
        self.assertEqual(raised.exception.status_code, 404)


if __name__ == "__main__":
    unittest.main()
