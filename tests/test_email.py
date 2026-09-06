import unittest
from unittest.mock import MagicMock, patch

from receptionist.email import Email, EmailSender


class EmailSenderTest(unittest.IsolatedAsyncioTestCase):
    async def test_sends_through_cloudflare(self) -> None:
        response = MagicMock(status=200)
        response.__aenter__.return_value = response
        session = MagicMock()
        session.__aenter__.return_value = session
        session.post.return_value = response

        with patch("receptionist.email.aiohttp.ClientSession", return_value=session):
            await EmailSender(
                "token", "a" * 32, "Receptionist <receptionist@example.com>", "to@example.com"
            ).send(Email("Subject", "Body"))

        session.post.assert_called_once_with(
            f"https://api.cloudflare.com/client/v4/accounts/{'a' * 32}/email/sending/send",
            headers={"authorization": "Bearer token", "content-type": "application/json"},
            json={
                "from": "Receptionist <receptionist@example.com>",
                "to": "to@example.com",
                "subject": "Subject",
                "text": "Body",
            },
        )


if __name__ == "__main__":
    unittest.main()
