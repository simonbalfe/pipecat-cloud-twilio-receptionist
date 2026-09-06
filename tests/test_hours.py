import unittest
from datetime import datetime, time
from zoneinfo import ZoneInfo

from receptionist.hours import BusinessHours, is_business_open


def business_hours() -> BusinessHours:
    return BusinessHours(
        timezone=ZoneInfo("Europe/London"),
        weekdays=frozenset(range(5)),
        opens=time(9),
        closes=time(17),
    )


class BusinessHoursTest(unittest.TestCase):
    def test_weekday_open_boundary(self) -> None:
        hours = business_hours()
        zone = ZoneInfo("Europe/London")
        self.assertTrue(is_business_open(hours, datetime(2026, 9, 7, 9, 0, tzinfo=zone)))
        self.assertFalse(is_business_open(hours, datetime(2026, 9, 7, 17, 0, tzinfo=zone)))

    def test_weekend_is_closed(self) -> None:
        hours = business_hours()
        zone = ZoneInfo("Europe/London")
        self.assertFalse(is_business_open(hours, datetime(2026, 9, 6, 12, 0, tzinfo=zone)))

    def test_invalid_schedule_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            BusinessHours(ZoneInfo("Europe/London"), frozenset(), time(9), time(17))
        with self.assertRaises(ValueError):
            BusinessHours(ZoneInfo("Europe/London"), frozenset(range(5)), time(17), time(9))


if __name__ == "__main__":
    unittest.main()
