import base64
import json
from dataclasses import dataclass
from typing import Self, cast
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


class TwilioError(RuntimeError):
    pass


@dataclass(frozen=True)
class TwilioNumber:
    sid: str
    trunk_sid: str | None

    @classmethod
    def from_api_response(cls, payload: object) -> Self:
        if not isinstance(payload, dict):
            raise TwilioError("Twilio returned an invalid phone-number response")
        response = cast(dict[str, object], payload)
        numbers_value = response.get("incoming_phone_numbers")
        if not isinstance(numbers_value, list):
            raise TwilioError("Twilio phone number was not found or was not unique")
        numbers = cast(list[object], numbers_value)
        if len(numbers) != 1 or not isinstance(numbers[0], dict):
            raise TwilioError("Twilio phone number was not found or was not unique")
        item = cast(dict[str, object], numbers[0])
        sid = item.get("sid")
        trunk_sid = item.get("trunk_sid")
        if not isinstance(sid, str) or not sid.startswith("PN"):
            raise TwilioError("Twilio returned an invalid phone-number SID")
        if trunk_sid is not None and not isinstance(trunk_sid, str):
            raise TwilioError("Twilio returned an invalid trunk SID")
        return cls(sid=sid, trunk_sid=trunk_sid or None)


def build_voice_url(agent_name: str, organization: str) -> str:
    service_host = f"{agent_name}.{organization}"
    twiml = (
        '<Response><Connect><Stream url="wss://api.pipecat.daily.co/ws/twilio">'
        f'<Parameter name="_pipecatCloudServiceHost" value="{service_host}"/>'
        "</Stream></Connect></Response>"
    )
    return f"https://twimlets.com/echo?{urlencode({'Twiml': twiml})}"


@dataclass(frozen=True)
class TwilioProvisioner:
    account_sid: str
    api_key: str
    api_secret: str

    def find_number(self, phone_number: str) -> TwilioNumber:
        query = urlencode({"PhoneNumber": phone_number, "PageSize": "2"})
        url = (
            f"https://api.twilio.com/2010-04-01/Accounts/{self.account_sid}"
            f"/IncomingPhoneNumbers.json?{query}"
        )
        return TwilioNumber.from_api_response(self._request_json(url))

    def connect(self, number: TwilioNumber, agent_name: str, organization: str) -> None:
        if number.trunk_sid:
            trunk_url = (
                f"https://trunking.twilio.com/v1/Trunks/{number.trunk_sid}"
                f"/PhoneNumbers/{number.sid}"
            )
            self._request_json(trunk_url, method="DELETE")
        number_url = (
            f"https://api.twilio.com/2010-04-01/Accounts/{self.account_sid}"
            f"/IncomingPhoneNumbers/{number.sid}.json"
        )
        self._request_json(
            number_url,
            method="POST",
            form={
                "FriendlyName": "Pipecat receptionist",
                "VoiceMethod": "GET",
                "VoiceUrl": build_voice_url(agent_name, organization),
            },
        )

    def _request_json(
        self,
        url: str,
        *,
        method: str = "GET",
        form: dict[str, str] | None = None,
    ) -> object:
        token = base64.b64encode(f"{self.api_key}:{self.api_secret}".encode()).decode()
        data = urlencode(form).encode() if form is not None else None
        request = Request(  # noqa: S310
            url,
            data=data,
            method=method,
            headers={"Authorization": f"Basic {token}"},
        )
        if data is not None:
            request.add_header("Content-Type", "application/x-www-form-urlencoded")
        try:
            with urlopen(request, timeout=20) as response:  # noqa: S310
                body = response.read()
        except HTTPError as error:
            raise TwilioError(
                f"Twilio returned HTTP {error.code} for {method} {request.full_url}"
            ) from error
        except URLError as error:
            raise TwilioError(f"Twilio request failed for {request.full_url}") from error
        if not body:
            return None
        try:
            return json.loads(body)
        except json.JSONDecodeError as error:
            raise TwilioError("Twilio returned invalid JSON") from error
