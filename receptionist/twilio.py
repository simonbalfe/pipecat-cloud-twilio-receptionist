from dataclasses import dataclass

import aiohttp


class TwilioCallError(RuntimeError):
    pass


@dataclass(frozen=True)
class TwilioCalls:
    account_sid: str
    api_key: str
    api_secret: str

    async def transfer(self, call_sid: str, phone_number: str) -> None:
        url = f"https://api.twilio.com/2010-04-01/Accounts/{self.account_sid}/Calls/{call_sid}.json"
        try:
            async with (
                aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10)) as session,
                session.post(
                    url,
                    auth=aiohttp.BasicAuth(self.api_key, self.api_secret),
                    data={"Twiml": f"<Response><Dial>{phone_number}</Dial></Response>"},
                ) as response,
            ):
                if response.status >= 300:
                    raise TwilioCallError(f"Twilio returned HTTP {response.status}")
        except (TimeoutError, aiohttp.ClientError) as error:
            raise TwilioCallError("Twilio request failed") from error
