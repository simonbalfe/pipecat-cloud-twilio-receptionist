from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import cast

from pipecat.adapters.schemas.function_schema import FunctionSchema
from pipecat.adapters.schemas.tools_schema import ToolsSchema
from pipecat.frames.frames import EndFrame
from pipecat.pipeline.worker import PipelineWorker
from pipecat.services.llm_service import FunctionCallParams
from pydantic import BaseModel, Field, ValidationError

from receptionist.email import Email, EmailDeliveryError, EmailSender


class Enquiry(BaseModel):
    property_type: str = Field(min_length=1)
    service: str = Field(min_length=1)
    address: str = Field(min_length=1)


@dataclass(frozen=True)
class CallTools:
    email: EmailSender
    caller_phone: str
    worker: PipelineWorker
    surveyor_message: str

    def schema(self) -> ToolsSchema:
        enquiry_schema = Enquiry.model_json_schema()
        properties = cast(dict[str, object], enquiry_schema["properties"])
        required = cast(list[str], enquiry_schema["required"])
        return ToolsSchema(
            standard_tools=[
                FunctionSchema(
                    name="notify_surveyor_call",
                    description=(
                        "Send the surveyor-call email after the caller confirms they are a "
                        "surveyor and agrees to hear the surveyor message."
                    ),
                    properties={},
                    required=[],
                ),
                FunctionSchema(
                    name="submit_property_enquiry",
                    description=(
                        "Email a completed non-surveyor enquiry after collecting property type, "
                        "required service, and full property address."
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
            await self.email.send(
                Email(
                    subject="Surveyor called the receptionist",
                    text=(
                        f"Caller: {self.caller_phone}\n\nMessage provided:\n{self.surveyor_message}"
                    ),
                )
            )
        except EmailDeliveryError:
            await params.result_callback({"status": "email_failed"})
            return
        await params.result_callback(
            {"status": "sent", "message_to_read_verbatim": self.surveyor_message}
        )

    async def submit_property_enquiry(self, params: FunctionCallParams) -> None:
        try:
            enquiry = Enquiry.model_validate(dict(params.arguments))
        except ValidationError:
            await params.result_callback({"status": "invalid_details"})
            return

        try:
            await self.email.send(
                Email(
                    subject=f"New {enquiry.service} enquiry",
                    text=(
                        f"Caller: {self.caller_phone}\n"
                        f"Property: {enquiry.property_type}\n"
                        f"Service: {enquiry.service}\n"
                        f"Address: {enquiry.address}"
                    ),
                )
            )
        except EmailDeliveryError:
            await params.result_callback({"status": "email_failed"})
            return
        await params.result_callback({"status": "sent"})

    async def end_call(self, params: FunctionCallParams) -> None:
        await params.result_callback({"status": "ending"})
        await self.worker.queue_frame(EndFrame())
