import logging
from dataclasses import dataclass

import aiohttp

logger = logging.getLogger(__name__)


class EmailDeliveryError(RuntimeError):
    pass


@dataclass(frozen=True)
class Email:
    subject: str
    text: str


@dataclass(frozen=True)
class EmailSender:
    api_token: str
    account_id: str
    sender: str
    recipient: str

    async def send(self, email: Email) -> None:
        headers = {
            "authorization": f"Bearer {self.api_token}",
            "content-type": "application/json",
        }
        payload = {
            "from": self.sender,
            "to": self.recipient,
            "subject": email.subject,
            "text": email.text,
        }
        timeout = aiohttp.ClientTimeout(total=10)
        try:
            async with (
                aiohttp.ClientSession(timeout=timeout) as session,
                session.post(
                    "https://api.cloudflare.com/client/v4/accounts/"
                    f"{self.account_id}/email/sending/send",
                    headers=headers,
                    json=payload,
                ) as response,
            ):
                if response.status >= 300:
                    detail = (await response.text())[:500]
                    raise EmailDeliveryError(
                        f"Cloudflare Email Sending returned HTTP {response.status}: {detail}"
                    )
        except (TimeoutError, aiohttp.ClientError) as error:
            raise EmailDeliveryError("Cloudflare Email Sending request failed") from error
