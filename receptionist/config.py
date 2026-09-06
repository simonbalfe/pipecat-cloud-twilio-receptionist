from datetime import time
from functools import lru_cache
from typing import Annotated, Self
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import AfterValidator, Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def _e164(value: str) -> str:
    if not value.startswith("+") or not value[1:].isdigit() or not 8 <= len(value[1:]) <= 15:
        raise ValueError("must be an E.164 phone number, for example +447700900000")
    return value


E164Phone = Annotated[str, AfterValidator(_e164)]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    deepgram_api_key: str = Field(min_length=1)
    deepgram_voice: str = "aura-2-helena-en"
    openrouter_api_key: str = Field(min_length=1)
    openrouter_model: str = "google/gemini-2.5-flash-lite"

    twilio_account_sid: str = Field(pattern=r"^AC[0-9a-f]{32}$")
    twilio_api_key: str = Field(pattern=r"^SK[0-9a-f]{32}$")
    twilio_api_secret: str = Field(min_length=1)

    business_name: str = "Property Surveyor"
    business_timezone: str = "Europe/London"
    business_weekdays: frozenset[int] = frozenset(range(5))
    business_opens: time = time(9)
    business_closes: time = time(17)
    owner_phone: E164Phone
    surveyor_message: str = Field(min_length=1)

    resend_api_key: str = Field(min_length=1)
    email_from: str = Field(min_length=3)
    email_to: str = Field(min_length=3)

    @field_validator("business_timezone")
    @classmethod
    def valid_timezone(cls, value: str) -> str:
        try:
            ZoneInfo(value)
        except ZoneInfoNotFoundError as error:
            raise ValueError(f"unknown timezone: {value}") from error
        return value

    @field_validator("business_weekdays")
    @classmethod
    def valid_weekdays(cls, value: frozenset[int]) -> frozenset[int]:
        if not value or not value <= set(range(7)):
            raise ValueError("must contain weekday numbers from 0 (Monday) to 6 (Sunday)")
        return value

    @model_validator(mode="after")
    def closes_after_open(self) -> Self:
        if self.business_closes <= self.business_opens:
            raise ValueError("must be later than BUSINESS_OPENS")
        return self


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()  # pyright: ignore[reportCallIssue]
