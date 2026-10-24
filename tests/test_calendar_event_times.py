import unittest

from app.routers.dashboard import CalendarEventTimeUpdate


class CalendarEventTimeTests(unittest.TestCase):
    def test_accepts_hour_and_minute_value(self):
        request = CalendarEventTimeUpdate(
            event_id="local-event-1",
            event_type="local",
            time="14:30",
        )

        self.assertEqual(request.time.strftime("%H:%M"), "14:30")


if __name__ == "__main__":
    unittest.main()
