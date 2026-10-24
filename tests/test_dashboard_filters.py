import json
import unittest
from unittest.mock import patch

from pydantic import ValidationError

from app.routers import config


class DashboardFilterConfigTests(unittest.TestCase):
    def test_filter_config_accepts_text_select_and_date_conditions(self):
        value = config.DashboardFilterConfig(conditions=[
            {"column": "company", "operator": "contains", "value": "科技"},
            {"column": "progress", "operator": "equals", "value": "面试"},
            {"column": "interview1", "operator": "range", "from": "2026-08-01", "to": "2026-08-31"},
        ])
        dumped = value.model_dump(by_alias=True, mode="json")
        self.assertEqual(dumped["conditions"][2]["from"], "2026-08-01")

    def test_filter_config_rejects_entry_column(self):
        with self.assertRaises(ValidationError):
            config.DashboardFilterConfig(conditions=[
                {"column": "url", "operator": "contains", "value": "example"},
            ])

    def test_saved_filters_are_scoped_to_current_user(self):
        value = config.DashboardFilterConfig(conditions=[
            {"column": "city", "operator": "equals", "value": "上海"},
        ])
        with patch("app.routers.config.database.save_dashboard_filters") as save:
            result = config.save_dashboard_filters(value, {"user_id": 7})
        save.assert_called_once()
        user_id, payload = save.call_args.args
        self.assertEqual(user_id, 7)
        self.assertEqual(json.loads(payload)[0]["value"], "上海")
        self.assertTrue(result["success"])


if __name__ == "__main__":
    unittest.main()
