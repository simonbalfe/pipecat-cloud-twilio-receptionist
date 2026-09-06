import unittest
from datetime import datetime
from zoneinfo import ZoneInfo

from receptionist.config import Settings
from receptionist.hours import is_business_open


def settings() -> Settings:
    return Settings.model_validate(
        {
            "deepgram_api_key": "test",
            "deepgram_voice": "test",
            "openrouter_api_key": "test",
            "twilio_account_sid": f"AC{'0' * 32}",
            "twilio_api_key": f"SK{'0' * 32}",
            "twilio_api_secret": "test",
            "owner_phone": "+447700900000",
            "surveyor_message": "Test message",
            "resend_api_key": "test",
            "email_from": "test@example.com",
            "email_to": "office@example.com",
        }
    )


class BusinessHoursTest(unittest.TestCase):
    def test_weekday_open_boundary(self) -> None:
        config = settings()
        zone = ZoneInfo("Europe/London")
        self.assertTrue(is_business_open(config, datetime(2026, 9, 7, 9, 0, tzinfo=zone)))
        self.assertFalse(is_business_open(config, datetime(2026, 9, 7, 17, 0, tzinfo=zone)))

    def test_weekend_is_closed(self) -> None:
        config = settings()
        zone = ZoneInfo("Europe/London")
        self.assertFalse(is_business_open(config, datetime(2026, 9, 6, 12, 0, tzinfo=zone)))


if __name__ == "__main__":
    unittest.main()
