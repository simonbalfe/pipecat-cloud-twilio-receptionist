import unittest
from urllib.parse import parse_qs, urlparse

from scripts.setup import (
    SetupError,
    _parse_twilio_number,  # pyright: ignore[reportPrivateUsage]
    _twimlet_url,  # pyright: ignore[reportPrivateUsage]
)


class SetupTest(unittest.TestCase):
    def test_twilio_route(self) -> None:
        number = _parse_twilio_number(
            {
                "incoming_phone_numbers": [
                    {"sid": "PN01234567890123456789012345678901", "trunk_sid": "TKold"}
                ]
            }
        )
        self.assertEqual(number.trunk_sid, "TKold")
        twiml = parse_qs(urlparse(_twimlet_url("my-agent", "my-org")).query)["Twiml"][0]
        self.assertIn('value="my-agent.my-org"', twiml)

    def test_rejects_ambiguous_number(self) -> None:
        with self.assertRaises(SetupError):
            _parse_twilio_number({"incoming_phone_numbers": []})


if __name__ == "__main__":
    unittest.main()
