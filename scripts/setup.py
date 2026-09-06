import base64
import json
import logging
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import cast
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from pydantic import Field

from receptionist.config import E164Phone, Settings

ROOT = Path(__file__).resolve().parents[1]

logger = logging.getLogger(__name__)


class SetupError(RuntimeError):
    pass


class SetupSettings(Settings):
    pipecat_token: str = Field(min_length=1)
    pipecat_agent_name: str = Field(pattern=r"^[a-z0-9][a-z0-9-]*$")
    pipecat_organization: str = Field(pattern=r"^[a-z0-9][a-z0-9-]*$")
    pipecat_region: str = "us-west"
    twilio_phone_number: E164Phone


@dataclass(frozen=True)
class TwilioNumber:
    sid: str
    trunk_sid: str | None


def _request_json(
    url: str,
    settings: SetupSettings,
    *,
    method: str = "GET",
    form: dict[str, str] | None = None,
) -> object:
    token = base64.b64encode(
        f"{settings.twilio_api_key}:{settings.twilio_api_secret}".encode()
    ).decode()
    data = urlencode(form).encode() if form is not None else None
    request = Request(  # noqa: S310
        url, data=data, method=method, headers={"Authorization": f"Basic {token}"}
    )
    if data is not None:
        request.add_header("Content-Type", "application/x-www-form-urlencoded")
    try:
        with urlopen(request, timeout=20) as response:  # noqa: S310
            body = response.read()
    except HTTPError as error:
        raise SetupError(
            f"Twilio returned HTTP {error.code} for {method} {request.full_url}"
        ) from error
    except URLError as error:
        raise SetupError(f"Twilio request failed for {request.full_url}") from error
    if not body:
        return None
    try:
        return json.loads(body)
    except json.JSONDecodeError as error:
        raise SetupError("Twilio returned invalid JSON") from error


def _parse_twilio_number(payload: object) -> TwilioNumber:
    if not isinstance(payload, dict):
        raise SetupError("Twilio returned an invalid phone-number response")
    response = cast(dict[str, object], payload)
    numbers_value = response.get("incoming_phone_numbers")
    if not isinstance(numbers_value, list):
        raise SetupError("Twilio phone number was not found or was not unique")
    numbers = cast(list[object], numbers_value)
    if len(numbers) != 1 or not isinstance(numbers[0], dict):
        raise SetupError("Twilio phone number was not found or was not unique")
    item = cast(dict[str, object], numbers[0])
    sid = item.get("sid")
    trunk_sid = item.get("trunk_sid")
    if not isinstance(sid, str) or not sid.startswith("PN"):
        raise SetupError("Twilio returned an invalid phone-number SID")
    if trunk_sid is not None and not isinstance(trunk_sid, str):
        raise SetupError("Twilio returned an invalid trunk SID")
    return TwilioNumber(sid=sid, trunk_sid=trunk_sid or None)


def _find_twilio_number(settings: SetupSettings) -> TwilioNumber:
    query = urlencode({"PhoneNumber": settings.twilio_phone_number, "PageSize": "2"})
    url = (
        f"https://api.twilio.com/2010-04-01/Accounts/{settings.twilio_account_sid}"
        f"/IncomingPhoneNumbers.json?{query}"
    )
    return _parse_twilio_number(_request_json(url, settings))


def _twimlet_url(agent_name: str, organization: str) -> str:
    service_host = f"{agent_name}.{organization}"
    twiml = (
        '<Response><Connect><Stream url="wss://api.pipecat.daily.co/ws/twilio">'
        f'<Parameter name="_pipecatCloudServiceHost" value="{service_host}"/>'
        "</Stream></Connect></Response>"
    )
    return f"https://twimlets.com/echo?{urlencode({'Twiml': twiml})}"


def _configure_twilio(settings: SetupSettings, number: TwilioNumber) -> None:
    if number.trunk_sid:
        trunk_url = (
            f"https://trunking.twilio.com/v1/Trunks/{number.trunk_sid}/PhoneNumbers/{number.sid}"
        )
        _request_json(trunk_url, settings, method="DELETE")
    number_url = (
        f"https://api.twilio.com/2010-04-01/Accounts/{settings.twilio_account_sid}"
        f"/IncomingPhoneNumbers/{number.sid}.json"
    )
    _request_json(
        number_url,
        settings,
        method="POST",
        form={
            "FriendlyName": "Pipecat receptionist",
            "VoiceMethod": "GET",
            "VoiceUrl": _twimlet_url(
                settings.pipecat_agent_name,
                settings.pipecat_organization,
            ),
        },
    )


def _runtime_secrets(settings: SetupSettings) -> dict[str, str]:
    return {
        "DEEPGRAM_API_KEY": settings.deepgram_api_key,
        "DEEPGRAM_VOICE": settings.deepgram_voice,
        "OPENROUTER_API_KEY": settings.openrouter_api_key,
        "OPENROUTER_MODEL": settings.openrouter_model,
        "TWILIO_ACCOUNT_SID": settings.twilio_account_sid,
        "TWILIO_API_KEY": settings.twilio_api_key,
        "TWILIO_API_SECRET": settings.twilio_api_secret,
        "BUSINESS_NAME": settings.business_name,
        "BUSINESS_TIMEZONE": settings.business_timezone,
        "BUSINESS_WEEKDAYS": json.dumps(sorted(settings.business_weekdays)),
        "BUSINESS_OPENS": settings.business_opens.isoformat(timespec="minutes"),
        "BUSINESS_CLOSES": settings.business_closes.isoformat(timespec="minutes"),
        "OWNER_PHONE": settings.owner_phone,
        "SURVEYOR_MESSAGE": settings.surveyor_message,
        "RESEND_API_KEY": settings.resend_api_key,
        "EMAIL_FROM": settings.email_from,
        "EMAIL_TO": settings.email_to,
    }


def _write_runtime_secrets(settings: SetupSettings, target: Path) -> None:
    lines = [f"{name}={json.dumps(value)}" for name, value in _runtime_secrets(settings).items()]
    target.write_text("\n".join(lines) + "\n")
    target.chmod(0o600)


def _run_pipecat(settings: SetupSettings, secrets_file: Path) -> None:
    secret_set = f"{settings.pipecat_agent_name}-secrets"
    environment = os.environ.copy()
    environment["PIPECAT_TOKEN"] = settings.pipecat_token
    environment["PIPECAT_ORG"] = settings.pipecat_organization
    commands = (
        [
            "uv",
            "run",
            "pipecat",
            "cloud",
            "secrets",
            "set",
            secret_set,
            "--file",
            str(secrets_file),
            "--skip",
            "--organization",
            settings.pipecat_organization,
            "--region",
            settings.pipecat_region,
        ],
        [
            "uv",
            "run",
            "pipecat",
            "cloud",
            "deploy",
            settings.pipecat_agent_name,
            "--build-dir",
            ".",
            "--secrets",
            secret_set,
            "--organization",
            settings.pipecat_organization,
            "--region",
            settings.pipecat_region,
            "--profile",
            "agent-1x",
            "--min-agents",
            "0",
            "--max-agents",
            "5",
            "--yes",
        ],
    )
    try:
        for command in commands:
            subprocess.run(command, cwd=ROOT, env=environment, check=True)  # noqa: S603
    except subprocess.CalledProcessError as error:
        raise SetupError("Pipecat Cloud setup failed; check the command output above") from error


def main() -> None:
    env_file = ROOT / ".env"
    if not env_file.is_file():
        raise SetupError("Copy .env.example to .env and fill every value first")
    settings = SetupSettings(_env_file=env_file)  # pyright: ignore[reportCallIssue]
    logger.info("Checking Twilio number %s", settings.twilio_phone_number)
    number = _find_twilio_number(settings)
    with TemporaryDirectory(prefix="pipecat-setup-") as temp_dir:
        secrets_file = Path(temp_dir) / "runtime.env"
        _write_runtime_secrets(settings, secrets_file)
        logger.info("Deploying %s to Pipecat Cloud", settings.pipecat_agent_name)
        _run_pipecat(settings, secrets_file)
    logger.info("Connecting Twilio number to Pipecat Cloud")
    _configure_twilio(settings, number)
    logger.info("Ready: call %s", settings.twilio_phone_number)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    try:
        main()
    except SetupError as error:
        raise SystemExit(str(error)) from error
