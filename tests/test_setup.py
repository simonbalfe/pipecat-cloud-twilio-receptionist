import unittest
from urllib.parse import parse_qs, urlparse

from scripts.twilio import TwilioError, TwilioNumber, build_voice_url


class SetupTest(unittest.TestCase):
    def test_twilio_route(self) -> None:
        number = TwilioNumber.from_api_response(
            {
                "incoming_phone_numbers": [
                    {"sid": "PN01234567890123456789012345678901", "trunk_sid": "TKold"}
                ]
            }
        )
        self.assertEqual(number.trunk_sid, "TKold")
        twiml = parse_qs(urlparse(build_voice_url("my-agent", "my-org")).query)["Twiml"][0]
        self.assertIn('value="my-agent.my-org"', twiml)

    def test_rejects_ambiguous_number(self) -> None:
        with self.assertRaises(TwilioError):
            TwilioNumber.from_api_response({"incoming_phone_numbers": []})


if __name__ == "__main__":
    unittest.main()
