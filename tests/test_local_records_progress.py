import unittest

from app.local_records import _sync_progress_with_dates


class ProgressDateSyncTests(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
