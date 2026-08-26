import unittest
from unittest.mock import patch

from app.local_records import _sync_progress_with_dates, get_dashboard_data


class ProgressDateSyncTests(unittest.TestCase):
    @patch("app.local_records._now_ms", return_value=456)
    def test_progress_advance_fills_destination_stage_date(self, _now):
        fields = _sync_progress_with_dates(
            {"进展": ["机考"], "机考时间": None},
            {"进展": ["已投递"], "投递时间": 123, "机考时间": None},
        )
        self.assertEqual(fields["进展"], ["机考"])
        self.assertEqual(fields["机考时间"], 456)

    @patch("app.local_records._now_ms", return_value=456)
    def test_progress_advance_does_not_replace_existing_stage_date(self, _now):
        fields = _sync_progress_with_dates(
            {"进展": ["面试"], "一面": None, "二面": 321},
            {"进展": ["机考"], "机考时间": 123, "二面": 321},
        )
        self.assertIsNone(fields["一面"])
        self.assertEqual(fields["二面"], 321)

    @patch("app.local_records._now_ms", return_value=456)
    def test_progress_advance_to_offer_fills_result_date(self, _now):
        fields = _sync_progress_with_dates(
            {"进展": ["OC"], "结果": None},
            {"进展": ["面试"], "一面": 123, "结果": None},
        )
        self.assertEqual(fields["结果"], 456)

    @patch("app.local_records._now_ms", return_value=456)
    def test_progress_rollback_clears_later_stage_dates(self, _now):
        fields = _sync_progress_with_dates(
            {"进展": ["已投递"]},
            {
                "进展": ["面试"],
                "投递时间": 100,
                "机考时间": 200,
                "一面": 300,
                "结果": None,
            },
        )
        self.assertEqual(fields["进展"], ["已投递"])
        self.assertNotIn("投递时间", fields)
        self.assertIsNone(fields["机考时间"])
        self.assertIsNone(fields["一面"])
        self.assertIsNone(fields["结果"])

    def test_progress_rollback_to_interview_only_clears_result_date(self):
        fields = _sync_progress_with_dates(
            {"进展": ["面试"]},
            {"进展": ["OC"], "投递时间": 100, "一面": 300, "结果": 400},
        )
        self.assertEqual(fields["进展"], ["面试"])
        self.assertNotIn("一面", fields)
        self.assertIsNone(fields["结果"])

    def test_apply_date_promotes_unapplied_record(self):
        fields = _sync_progress_with_dates(
            {"投递时间": 123}, {"进展": ["未投递"]}
        )
        self.assertEqual(fields["进展"], ["已投递"])

    def test_interview_date_promotes_past_earlier_stages(self):
        fields = _sync_progress_with_dates(
            {"二面": 123}, {"进展": ["机考"], "投递时间": 100}
        )
        self.assertEqual(fields["进展"], ["面试"])

    def test_earlier_date_does_not_roll_back_terminal_progress(self):
        fields = _sync_progress_with_dates(
            {"机考时间": 123}, {"进展": ["OC"]}
        )
        self.assertNotIn("进展", fields)

    def test_cleared_dates_do_not_promote_progress(self):
        fields = _sync_progress_with_dates(
            {"进展": ["未投递"], "投递时间": None},
            {"进展": ["已投递"], "投递时间": 123},
        )
        self.assertEqual(fields["进展"], ["未投递"])

    def test_clearing_interview_falls_back_to_remaining_exam(self):
        fields = _sync_progress_with_dates(
            {"一面": None},
            {"进展": ["面试"], "投递时间": 100, "机考时间": 200, "一面": 300},
        )
        self.assertEqual(fields["进展"], ["机考"])

    def test_clearing_date_does_not_roll_back_terminal_progress(self):
        fields = _sync_progress_with_dates(
            {"三面": None}, {"进展": ["OC"], "三面": 300}
        )
        self.assertNotIn("进展", fields)

    def test_kpis_count_company_once_across_child_records(self):
        def record(record_id, company, progress, **dates):
            fields = {"公司名称": company, "进展": [progress], "嵌入式方向": [], "公司/行业类型": []}
            fields.update(dates)
            return {"record_id": record_id, "fields": fields}

        records = [
            record("r1", "示例公司", "机考", 投递时间=1, 机考时间=2),
            record("r2", " 示例公司 ", "OC", 投递时间=1, 一面=3),
            record("r3", "另一家公司", "面试", 投递时间=1, 一面=4),
        ]
        with patch("app.local_records.list_records", return_value=records):
            main = get_dashboard_data(1)["main"]
        self.assertEqual(main["total_companies"], 2)
        self.assertEqual(main["exam_count"], 1)
        self.assertEqual(main["interview_count"], 2)
        self.assertEqual(main["offer_count"], 1)


if __name__ == "__main__":
    unittest.main()
