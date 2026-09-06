import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from receptionist.twilio import TwilioCalls


class TwilioCallsTest(unittest.IsolatedAsyncioTestCase):
    async def test_reads_caller_number(self) -> None:
        response = MagicMock(status=200)
        response.json = AsyncMock(return_value={"from": "+447700900000"})
        response.__aenter__.return_value = response
        session = MagicMock()
        session.__aenter__.return_value = session
        session.request.return_value = response

        with patch("receptionist.twilio.aiohttp.ClientSession", return_value=session):
            caller = await TwilioCalls("account", "key", "secret").caller_phone("CA123")

        self.assertEqual(caller, "+447700900000")


if __name__ == "__main__":
    unittest.main()
