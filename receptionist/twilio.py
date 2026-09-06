from dataclasses import dataclass

import aiohttp
from pipecat.serializers.twilio import TwilioFrameSerializer
from pydantic import BaseModel, Field, ValidationError


class TwilioCallError(RuntimeError):
    pass


class TwilioCall(BaseModel):
    from_number: str = Field(alias="from", min_length=1)


def create_twilio_serializer(stream_sid: str, call_sid: str | None) -> TwilioFrameSerializer:
    return TwilioFrameSerializer(
        stream_sid=stream_sid,
        call_sid=call_sid,
        params=TwilioFrameSerializer.InputParams(auto_hang_up=False),
    )


@dataclass(frozen=True)
class TwilioCalls:
    account_sid: str
    api_key: str
    api_secret: str

    async def caller_phone(self, call_sid: str) -> str:
        response = await self._request(call_sid)
        try:
            return TwilioCall.model_validate(response).from_number
        except ValidationError as error:
            raise TwilioCallError("Twilio returned invalid call details") from error

    async def transfer(self, call_sid: str, phone_number: str) -> None:
        await self._request(
            call_sid,
            data={"Twiml": f"<Response><Dial>{phone_number}</Dial></Response>"},
        )

    async def _request(self, call_sid: str, *, data: dict[str, str] | None = None) -> object:
        url = f"https://api.twilio.com/2010-04-01/Accounts/{self.account_sid}/Calls/{call_sid}.json"
        try:
            async with (
                aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10)) as session,
                session.request(
                    "POST" if data else "GET",
                    url,
                    auth=aiohttp.BasicAuth(self.api_key, self.api_secret),
                    data=data,
                ) as response,
            ):
                if response.status >= 300:
                    raise TwilioCallError(f"Twilio returned HTTP {response.status}")
                return await response.json(content_type=None)
        except (TimeoutError, aiohttp.ClientError) as error:
            raise TwilioCallError("Twilio request failed") from error
