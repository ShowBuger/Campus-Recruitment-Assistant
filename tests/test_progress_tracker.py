import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from app.routers import progress_tracker


def saved_record(progress):
    return {
        "record_id": "rec-1",
        "fields": {"进展": [progress]},
    }


class ProgressTrackerStateMachineTests(unittest.TestCase):
    def test_user_confirmed_time_overrides_detected_event_time(self):
        event = {
            "progress": "机考",
            "scheduled_ms": 1720000000000,
            "deadline_ms": 1720100000000,
            "_confirmed_event_ms": 1720200000000,
        }
        self.assertEqual(progress_tracker._record_event_time(event), 1720200000000)

    def test_exam_record_uses_deadline_instead_of_start_time(self):
        event = {
            "record_id": "rec-1",
            "progress": "机考",
            "received_ms": 1785203811000,
            "scheduled_ms": 1785409200000,
            "deadline_ms": 1785412800000,
        }
        with (
            patch(
                "app.routers.progress_tracker.local_records.get_record",
                return_value=saved_record("已投递"),
            ),
            patch(
                "app.routers.progress_tracker.local_records.update_record",
                return_value=True,
            ) as update,
            patch("app.routers.progress_tracker.local_records.get_dashboard_data"),
            patch("app.routers.progress_tracker.state.set_cache"),
        ):
            progress_tracker._apply_event(1, event)

        self.assertEqual(
            update.call_args.args[2]["机考时间"],
            event["deadline_ms"],
        )

    def test_explicit_beijing_exam_time_overrides_wrong_ai_epoch(self):
        result = {
            "progress": "机考",
            "scheduled_ms": 1785495600000,
            "deadline_ms": 1785499200000,
            "time_reason": "模型计算结果",
        }
        message = {
            "subject": "在线考试邀请函",
            "received_ms": 1785203811000,
            "body": (
                "开始时间（北京时间）： 2026-07-30 19:00 星期四 "
                "结束时间（北京时间）： 2026-07-30 20:00 星期四"
            ),
        }

        normalized = progress_tracker._normalize_result_times(result, message)

        china = timezone(timedelta(hours=8))
        expected_start = int(
            datetime(2026, 7, 30, 19, 0, tzinfo=china).timestamp() * 1000
        )
        expected_end = int(
            datetime(2026, 7, 30, 20, 0, tzinfo=china).timestamp() * 1000
        )
        self.assertEqual(normalized["scheduled_ms"], expected_start)
        self.assertEqual(normalized["deadline_ms"], expected_end)
        self.assertIn("邮件原文确定解析", normalized["time_reason"])

    def test_date_only_deadline_uses_end_of_china_day(self):
        result = {"progress": "机考", "deadline_ms": None}
        message = {
            "subject": "测评通知",
            "received_ms": 1785203811000,
            "body": "请于截止日期：7月30日前完成测评。",
        }

        normalized = progress_tracker._normalize_result_times(result, message)

        parsed = datetime.fromtimestamp(
            normalized["deadline_ms"] / 1000,
            tz=timezone(timedelta(hours=8)),
        )
        self.assertEqual(
            (parsed.year, parsed.month, parsed.day, parsed.hour, parsed.minute),
            (2026, 7, 30, 23, 59),
        )

    def test_delayed_lower_stage_only_backfills_date(self):
        event = {
            "record_id": "rec-1",
            "progress": "已投递",
            "received_ms": 1720000000000,
        }
        with (
            patch(
                "app.routers.progress_tracker.local_records.get_record",
                return_value=saved_record("面试"),
            ),
            patch(
                "app.routers.progress_tracker.local_records.update_record",
                return_value=True,
            ) as update,
            patch("app.routers.progress_tracker.local_records.get_dashboard_data"),
            patch("app.routers.progress_tracker.state.set_cache"),
        ):
            outcome = progress_tracker._apply_event(1, event)

        fields = update.call_args.args[2]
        self.assertEqual(fields["进展"], ["面试"])
        self.assertEqual(fields["投递时间"], event["received_ms"])
        self.assertEqual(outcome["previous_progress"], "面试")
        self.assertEqual(outcome["resulting_progress"], "面试")
        self.assertIn("保持面试", outcome["resolution"])

    def test_forward_stage_updates_progress_and_round_date(self):
        event = {
            "record_id": "rec-1",
            "progress": "面试",
            "received_ms": 1720000000000,
            "scheduled_ms": 1721000000000,
            "interview_round": 2,
        }
        with (
            patch(
                "app.routers.progress_tracker.local_records.get_record",
                return_value=saved_record("机考"),
            ),
            patch(
                "app.routers.progress_tracker.local_records.update_record",
                return_value=True,
            ) as update,
            patch("app.routers.progress_tracker.local_records.get_dashboard_data"),
            patch("app.routers.progress_tracker.state.set_cache"),
        ):
            outcome = progress_tracker._apply_event(1, event)

        fields = update.call_args.args[2]
        self.assertEqual(fields["进展"], ["面试"])
        self.assertEqual(fields["二面"], event["scheduled_ms"])
        self.assertNotIn("一面", fields)
        self.assertEqual(outcome["resulting_progress"], "面试")

    def test_terminal_state_is_not_reopened_by_automatic_event(self):
        event = {
            "record_id": "rec-1",
            "progress": "面试",
            "received_ms": 1720000000000,
        }
        with (
            patch(
                "app.routers.progress_tracker.local_records.get_record",
                return_value=saved_record("已挂"),
            ),
            patch(
                "app.routers.progress_tracker.local_records.update_record",
                return_value=True,
            ) as update,
            patch("app.routers.progress_tracker.local_records.get_dashboard_data"),
            patch("app.routers.progress_tracker.state.set_cache"),
        ):
            outcome = progress_tracker._apply_event(1, event)

        self.assertEqual(update.call_args.args[2]["进展"], ["已挂"])
        self.assertEqual(outcome["resulting_progress"], "已挂")


class ProgressTrackerCompanyMatchingTests(unittest.TestCase):
    def setUp(self):
        self.records = [{
            "record_id": "rec-company",
            "fields": {
                "公司名称": "北京星河科技有限公司",
                "秋招岗位": "嵌入式软件工程师",
            },
        }]

    def test_short_company_name_in_email_matches_legal_entity(self):
        score, record, company, _ = progress_tracker._match_company(
            "星河科技面试邀请 嵌入式软件工程师", self.records,
        )
        self.assertGreaterEqual(score, 2)
        self.assertEqual(record["record_id"], "rec-company")
        self.assertEqual(company, "北京星河科技有限公司")

    def test_ai_company_group_name_matches_saved_legal_entity(self):
        record_id, company, job = progress_tracker._match_ai_record(
            "北京星河科技集团", "嵌入式软件工程师", self.records,
        )
        self.assertEqual(record_id, "rec-company")
        self.assertEqual(company, "北京星河科技有限公司")
        self.assertEqual(job, "嵌入式软件工程师")

    def test_unrelated_company_does_not_match(self):
        record_id, _, _ = progress_tracker._match_ai_record(
            "远海银行", "嵌入式软件工程师", self.records,
        )
        self.assertIsNone(record_id)

    def test_local_match_selects_the_child_record_named_in_email(self):
        records = [
            {
                "record_id": "rec-embedded",
                "fields": {
                    "公司名称": "北京星河科技有限公司",
                    "秋招岗位": "嵌入式软件工程师",
                },
            },
            {
                "record_id": "rec-finance",
                "fields": {
                    "公司名称": "北京星河科技有限公司",
                    "秋招岗位": "财务管培生",
                },
            },
        ]

        score, record, _, job = progress_tracker._match_company(
            "星河科技嵌入式软件工程师二面通知", records,
        )

        self.assertEqual(score, 3)
        self.assertEqual(record["record_id"], "rec-embedded")
        self.assertEqual(job, "嵌入式软件工程师")

    def test_local_match_does_not_guess_between_same_company_children(self):
        records = [
            {
                "record_id": "rec-embedded",
                "fields": {
                    "公司名称": "北京星河科技有限公司",
                    "秋招岗位": "嵌入式软件工程师",
                },
            },
            {
                "record_id": "rec-finance",
                "fields": {
                    "公司名称": "北京星河科技有限公司",
                    "秋招岗位": "财务管培生",
                },
            },
        ]

        score, record, company, job = progress_tracker._match_company(
            "星河科技面试安排", records,
        )

        self.assertEqual(score, 2)
        self.assertIsNone(record)
        self.assertEqual(company, "北京星河科技有限公司")
        self.assertEqual(job, "")

    def test_ai_fallback_selects_unique_job_child(self):
        records = [
            {
                "record_id": "rec-embedded",
                "fields": {
                    "公司名称": "北京星河科技有限公司",
                    "秋招岗位": "嵌入式软件工程师",
                },
            },
            {
                "record_id": "rec-finance",
                "fields": {
                    "公司名称": "北京星河科技有限公司",
                    "秋招岗位": "财务管培生",
                },
            },
        ]

        record_id, _, job = progress_tracker._match_ai_record(
            "星河科技", "嵌入式软件工程师", records,
        )

        self.assertEqual(record_id, "rec-embedded")
        self.assertEqual(job, "嵌入式软件工程师")

    def test_ai_fallback_does_not_guess_without_job_between_children(self):
        records = [
            {
                "record_id": "rec-embedded",
                "fields": {
                    "公司名称": "北京星河科技有限公司",
                    "秋招岗位": "嵌入式软件工程师",
                },
            },
            {
                "record_id": "rec-finance",
                "fields": {
                    "公司名称": "北京星河科技有限公司",
                    "秋招岗位": "财务管培生",
                },
            },
        ]

        record_id, company, job = progress_tracker._match_ai_record(
            "星河科技", "", records,
        )

        self.assertIsNone(record_id)
        self.assertEqual(company, "星河科技")
        self.assertEqual(job, "")

    def test_apply_event_updates_only_matched_child_record(self):
        event = {
            "record_id": "rec-finance",
            "progress": "面试",
            "received_ms": 1720000000000,
        }
        finance_record = {
            "record_id": "rec-finance",
            "fields": {"公司名称": "星河科技", "秋招岗位": "财务管培生", "进展": ["已投递"]},
        }
        with (
            patch("app.routers.progress_tracker.local_records.get_record", return_value=finance_record) as get_record,
            patch("app.routers.progress_tracker.local_records.update_record", return_value=True) as update,
            patch("app.routers.progress_tracker.local_records.get_dashboard_data"),
            patch("app.routers.progress_tracker.state.set_cache"),
        ):
            progress_tracker._apply_event(1, event, interview_round=1)

        get_record.assert_called_once_with(1, "rec-finance")
        self.assertEqual(update.call_args.args[1], "rec-finance")
        self.assertEqual(update.call_args.args[2]["进展"], ["面试"])


if __name__ == "__main__":
    unittest.main()
