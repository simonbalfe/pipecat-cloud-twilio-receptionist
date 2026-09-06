import json
import logging
import os
import subprocess
from pathlib import Path
from tempfile import TemporaryDirectory

from pydantic import Field

from receptionist.config import E164Phone, Settings

from .twilio import TwilioError, TwilioProvisioner

ROOT = Path(__file__).resolve().parents[1]

logger = logging.getLogger(__name__)


class SetupError(RuntimeError):
    pass


class SetupSettings(Settings):
    pipecat_token: str = Field(min_length=1)
    pipecat_agent_name: str = Field(pattern=r"^[a-z0-9][a-z0-9-]*$")
    pipecat_organization: str = Field(pattern=r"^[a-z0-9][a-z0-9-]*$")
    pipecat_region: str = "us-west"
    pipecat_min_agents: int = Field(default=0, ge=0, le=5)
    twilio_phone_number: E164Phone


def _runtime_secrets(settings: SetupSettings) -> dict[str, str]:
    return {
        "DEEPGRAM_API_KEY": settings.deepgram_api_key,
        "DEEPGRAM_VOICE": settings.deepgram_voice,
        "OPENROUTER_API_KEY": settings.openrouter_api_key,
        "OPENROUTER_MODEL": settings.openrouter_model,
        "LLM_TEMPERATURE": str(settings.llm_temperature),
        "LLM_MAX_COMPLETION_TOKENS": str(settings.llm_max_completion_tokens),
        "USER_TURN_STOP_TIMEOUT": str(settings.user_turn_stop_timeout),
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
            str(settings.pipecat_min_agents),
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
    twilio = TwilioProvisioner(
        settings.twilio_account_sid,
        settings.twilio_api_key,
        settings.twilio_api_secret,
    )
    number = twilio.find_number(settings.twilio_phone_number)
    with TemporaryDirectory(prefix="pipecat-setup-") as temp_dir:
        secrets_file = Path(temp_dir) / "runtime.env"
        _write_runtime_secrets(settings, secrets_file)
        logger.info("Deploying %s to Pipecat Cloud", settings.pipecat_agent_name)
        _run_pipecat(settings, secrets_file)
    logger.info("Connecting Twilio number to Pipecat Cloud")
    twilio.connect(number, settings.pipecat_agent_name, settings.pipecat_organization)
    logger.info("Ready: call %s", settings.twilio_phone_number)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    try:
        main()
    except (SetupError, TwilioError) as error:
        raise SystemExit(str(error)) from error
