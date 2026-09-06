import unittest

from pipecat.serializers.twilio import TwilioFrameSerializer

from receptionist.twilio import create_twilio_serializer


class TwilioTransportTest(unittest.TestCase):
    def test_serializer_does_not_require_primary_auth_token(self) -> None:
        serializer = create_twilio_serializer("MZtest", "CAtest")
        self.assertIsInstance(serializer, TwilioFrameSerializer)


if __name__ == "__main__":
    unittest.main()
