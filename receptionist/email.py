from dataclasses import dataclass

import aiohttp


class EmailDeliveryError(RuntimeError):
    pass


@dataclass(frozen=True)
class Email:
    subject: str
    text: str


@dataclass(frozen=True)
class EmailSender:
    api_key: str
    sender: str
    recipient: str

    async def send(self, email: Email) -> None:
        headers = {"authorization": f"Bearer {self.api_key}", "content-type": "application/json"}
        payload = {
            "from": self.sender,
            "to": [self.recipient],
            "subject": email.subject,
            "text": email.text,
        }
        timeout = aiohttp.ClientTimeout(total=10)
        try:
            async with (
                aiohttp.ClientSession(timeout=timeout) as session,
                session.post(
                    "https://api.resend.com/emails", headers=headers, json=payload
                ) as response,
            ):
                if response.status >= 300:
                    raise EmailDeliveryError(f"Resend returned HTTP {response.status}")
        except (TimeoutError, aiohttp.ClientError) as error:
            raise EmailDeliveryError("Resend request failed") from error
