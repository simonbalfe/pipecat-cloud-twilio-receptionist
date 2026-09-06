from datetime import time
from functools import lru_cache
from typing import Annotated, Self
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import AfterValidator, Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from .hours import BusinessHours


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
    llm_temperature: float = Field(default=0.2, ge=0, le=2)
    llm_max_completion_tokens: int = Field(default=250, ge=1, le=1000)
    user_turn_stop_timeout: float = Field(default=0.8, gt=0, le=5)

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

    @model_validator(mode="after")
    def valid_business_hours(self) -> Self:
        _ = self.business_hours
        return self

    @property
    def business_hours(self) -> BusinessHours:
        return BusinessHours(
            timezone=ZoneInfo(self.business_timezone),
            weekdays=self.business_weekdays,
            opens=self.business_opens,
            closes=self.business_closes,
        )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()  # pyright: ignore[reportCallIssue]
