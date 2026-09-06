import asyncio
import logging
import re
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from enum import StrEnum
from typing import cast

from pipecat.adapters.schemas.function_schema import FunctionSchema
from pipecat.adapters.schemas.tools_schema import ToolsSchema
from pipecat.frames.frames import EndFrame
from pipecat.pipeline.worker import PipelineWorker
from pipecat.services.llm_service import FunctionCallParams
from pydantic import BaseModel, Field, ValidationError, field_validator

from receptionist.email import Email, EmailDeliveryError, EmailSender

logger = logging.getLogger(__name__)

DIGITS = {
    "zero": "0",
    "oh": "0",
    "one": "1",
    "two": "2",
    "three": "3",
    "four": "4",
    "five": "5",
    "six": "6",
    "seven": "7",
    "eight": "8",
    "nine": "9",
}


class Enquiry(BaseModel):
    property_type: str = Field(min_length=1)
    service: str = Field(min_length=1)
    address: str = Field(min_length=1)
    postcode: str = Field(min_length=5, max_length=8)

    @field_validator("postcode", mode="before")
    @classmethod
    def normalize_postcode(cls, value: object) -> str:
        if not isinstance(value, str):
            raise ValueError("invalid UK postcode")
        compact = "".join(
            DIGITS.get(part.lower()) or part for part in re.findall(r"[A-Za-z]+|\d+", value)
        ).upper()
        if not re.fullmatch(r"[A-Z]{1,2}\d[A-Z\d]?\d[A-Z]{2}", compact):
            raise ValueError("invalid UK postcode")
        return f"{compact[:-3]} {compact[-3:]}"


class SurveyorMessage(BaseModel):
    message: str = Field(min_length=1)


class CallStage(StrEnum):
    COLLECTING = "collecting"
    EMAIL_SENT = "email_sent"
    ENDING = "ending"


@dataclass
class CallTools:
    email: EmailSender
    caller_phone: str
    worker: PipelineWorker
    stage: CallStage = field(default=CallStage.COLLECTING, init=False)
    _stage_lock: asyncio.Lock = field(default_factory=asyncio.Lock, init=False, repr=False)

    def schema(self) -> ToolsSchema:
        enquiry_schema = Enquiry.model_json_schema()
        properties = cast(dict[str, object], enquiry_schema["properties"])
        required = cast(list[str], enquiry_schema["required"])
        surveyor_schema = SurveyorMessage.model_json_schema()
        return ToolsSchema(
            standard_tools=[
                FunctionSchema(
                    name="notify_surveyor_call",
                    description=(
                        "Send the surveyor's message after they have said what they want passed "
                        "to the office."
                    ),
                    properties=cast(dict[str, object], surveyor_schema["properties"]),
                    required=cast(list[str], surveyor_schema["required"]),
                ),
                FunctionSchema(
                    name="submit_property_enquiry",
                    description=(
                        "Email a completed non-surveyor enquiry after collecting property type, "
                        "required service, full property address, and confirmed UK postcode."
                    ),
                    properties=properties,
                    required=required,
                ),
                FunctionSchema(
                    name="end_call",
                    description="End the call after saying goodbye.",
                    properties={},
                    required=[],
                ),
            ]
        )

    def register(
        self, register: Callable[[str, Callable[[FunctionCallParams], Awaitable[None]]], None]
    ) -> None:
        register("notify_surveyor_call", self.notify_surveyor_call)
        register("submit_property_enquiry", self.submit_property_enquiry)
        register("end_call", self.end_call)

    async def notify_surveyor_call(self, params: FunctionCallParams) -> None:
        try:
            surveyor = SurveyorMessage.model_validate(dict(params.arguments))
        except ValidationError:
            await params.result_callback({"status": "invalid_message"})
            return

        await self._deliver_once(
            params,
            Email(
                subject="Surveyor called the receptionist",
                text=f"Caller: {self.caller_phone}\n\nMessage:\n{surveyor.message}",
            ),
            "Could not send surveyor email",
        )

    async def submit_property_enquiry(self, params: FunctionCallParams) -> None:
        try:
            enquiry = Enquiry.model_validate(dict(params.arguments))
        except ValidationError:
            await params.result_callback({"status": "invalid_details"})
            return

        await self._deliver_once(
            params,
            Email(
                subject=f"New {enquiry.service} enquiry",
                text=(
                    f"Caller: {self.caller_phone}\n"
                    f"Property: {enquiry.property_type}\n"
                    f"Service: {enquiry.service}\n"
                    f"Address: {enquiry.address}\n"
                    f"Postcode: {enquiry.postcode}"
                ),
            ),
            "Could not send property enquiry email",
        )

    async def _deliver_once(
        self, params: FunctionCallParams, email: Email, failure_log: str
    ) -> None:
        async with self._stage_lock:
            if self.stage is not CallStage.COLLECTING:
                await params.result_callback({"status": "already_sent"})
                return
            try:
                await self.email.send(email)
            except EmailDeliveryError:
                logger.exception(failure_log)
                await params.result_callback({"status": "email_failed"})
                return
            self.stage = CallStage.EMAIL_SENT
        await params.result_callback({"status": "sent"})

    async def end_call(self, params: FunctionCallParams) -> None:
        async with self._stage_lock:
            if self.stage is CallStage.ENDING:
                await params.result_callback({"status": "already_ending"})
                return
            self.stage = CallStage.ENDING
        await params.result_callback({"status": "ending"})
        await self.worker.queue_frame(EndFrame())
